#!/usr/bin/env python3
"""离线检索计划与证据案例检查；不会联网、上传或执行记录中的命令。"""

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


NOTICE = ("仅供人工复核；敏感信息检测不是完整保证。离线公开检索词策略仅允许无凭据的公网 HTTP(S) URI。"
          "工具不会联网、解析 DNS、上传或执行搜索结果。")
SOURCE_IDS = ("github_issues", "github_prs", "huggingface", "huggingface_forum", "zhihu", "xiaohongshu",
              "openreview", "pmlr", "cvf", "acl", "journals", "scholars", "labs")
LANGUAGE_IDS = ("en", "zh")
SECRET_PATTERNS = (
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    r"\b(?:hf_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{16,})",
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{8,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)
SENSITIVE_FIELD_WORDS = frozenset({"token", "secret", "password", "passwd", "passphrase", "pwd",
                                   "authorization", "bearer", "sig", "signature", "credential", "credentials"})
SENSITIVE_COMPACT_FIELDS = frozenset({"apikey", "accesskey", "accesskeyid", "awsaccesskeyid", "privatekey",
                                     "secretkey", "accesstoken", "refreshtoken", "idtoken", "authtoken", "clientsecret"})
ASSIGNMENT_FIELD_PATTERN = re.compile(
    r"(?<![\w-])([A-Za-z_][A-Za-z0-9_-]*(?:[ \t]+(?:key|token))?)[\"']?\s*[:=](?=\s*\S)", re.I
)
CLI_FIELD_PATTERN = re.compile(
    r"(?<![\w-])--([A-Za-z][A-Za-z0-9_-]*)[\"']?(?:\s*=\s*|\s+)(?=\S)"
)
# :// 明确标识 URI；常见非层级 URI 单独识别，避免把 RuntimeError: 或 C++ 命名空间当成 URI。
URI_PATTERN = re.compile(
    r"\b(?:[A-Za-z][A-Za-z0-9+.-]*://|(?:file|data|mailto|urn|tel|sms):)[^\s<>\"']+", re.I
)
PRIVATE_HOST_PATTERN = re.compile(
    r"(?i)\b(?:localhost|[a-z0-9-]+\.(?:local|internal|localhost|lan))(?::\d+)?(?:/|\b)"
)


def sensitive_field(name):
    """为赋值、CLI 选项和已解码的 URL 参数共用凭据字段规则。"""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    words = re.split(r"[\s_.-]+", name.lower().strip())
    if "".join(words) in SENSITIVE_COMPACT_FIELDS or any(
            word in SENSITIVE_FIELD_WORDS or word in SENSITIVE_COMPACT_FIELDS for word in words):
        return True
    return any("".join(words[index:index + 2]) in SENSITIVE_COMPACT_FIELDS for index in range(len(words) - 1))


def contains_credentials(value):
    if any(re.search(pattern, value) for pattern in SECRET_PATTERNS):
        return True
    return any(sensitive_field(match.group(1))
               for pattern in (ASSIGNMENT_FIELD_PATTERN, CLI_FIELD_PATTERN)
               for match in pattern.finditer(value))


def public_url(value):
    """只接受无凭据的公网 HTTP(S) URL；不发起 DNS 或网络请求。"""
    if not isinstance(value, str) or re.search(r"\s|[\\\x00-\x1f\x7f]", value):
        return False
    if contains_credentials(value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None:
            return False
        if parsed.password is not None or parsed.port == 0:
            return False
        fields = (parsed.query, parsed.fragment, parsed.fragment.partition("?")[2])
        if any(sensitive_field(key) for field in fields
               for key, _value in parse_qsl(field, keep_blank_values=True)):
            return False
        host = host.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            # 全数字、旧式十六进制 IP 或单标签主机不视为可信公网域名。
            if re.fullmatch(r"[0-9.]+|0x[0-9a-f]+", host):
                return False
            return bool(re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", host))
    except (ValueError, TypeError):
        return False


def safe_search_input(values):
    """按离线公开检索词策略拒绝明显凭据、私有 URL 和非 HTTP(S) URI。"""
    for value in values:
        if not isinstance(value, str) or contains_credentials(value):
            return False
        if PRIVATE_HOST_PATTERN.search(value):
            return False
        if any(not public_url(uri.group(0)) for uri in URI_PATTERN.finditer(value)):
            return False
        addresses = re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", value)
        addresses += re.findall(r"(?<!\w)(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*", value)
        for address in addresses:
            try:
                if not ipaddress.ip_address(address).is_global:
                    return False
            except ValueError:
                pass
    return True


def make_queries(error, component="", version="", concepts=None, source_filters=None,
                 language_filters=None, max_queries=None, repository=None):
    parts = [error, component, version, *(concepts or [])]
    if repository is not None:
        parts.append(repository)
    if not safe_search_input(parts):
        raise ValueError("检测到可能的凭据、私有 URL 或不支持的 URI，请脱敏后重试。" + NOTICE)
    if not error.strip():
        raise ValueError("报错或症状不能为空。")
    source_filters = source_filters or SOURCE_IDS
    language_filters = language_filters or LANGUAGE_IDS
    if any(not isinstance(source, str) or source not in SOURCE_IDS for source in source_filters):
        raise ValueError("检索来源无效；请使用 --help 中列出的来源。")
    if any(not isinstance(language, str) or language not in LANGUAGE_IDS for language in language_filters):
        raise ValueError("检索语言无效；请选择 en 或 zh。")
    if max_queries is not None and (type(max_queries) is not int or max_queries < 1):
        raise ValueError("候选查询数量上限必须是正整数。")
    if repository is not None and (not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9_.-]+", repository)
                                   or repository.rsplit("/", 1)[-1] in {".", ".."}):
        raise ValueError("仓库格式无效；请使用 owner/name。")
    source_filters = list(dict.fromkeys(source_filters))
    language_filters = list(dict.fromkeys(language_filters))
    concepts = [concept.strip() for concept in (concepts or []) if concept.strip()]
    precise = re.sub(r"\s+", " ", " ".join(part.strip() for part in [component, version, error] if part.strip()))
    mechanism = re.sub(r"\s+", " ", " ".join(part.strip() for part in [component, *(concepts or [error])] if part.strip()))
    mechanism_note = ("先从报错提炼机制与概念；缺少 --concept，此处报错仅为待人工改写的占位词。"
                      if not concepts else "按机制和概念检索；人工核对学科与方法是否适用。")
    sources = (
        ("github_issues", "site:github.com", "(issue OR bug OR workaround)", "(问题 OR 报错 OR 解决)", "寻找相同报错、复现步骤与维护者结论"),
        ("github_prs", "site:github.com", '("pull request" OR merged OR fix)', "(修复 OR 合并 OR 补丁)", "核对修复差异、合并状态与适用版本"),
        ("huggingface", "site:huggingface.co", "(discussion OR issue OR implementation)", "(讨论 OR 实现 OR 解决)", "查找模型、数据集、实现和讨论，核对许可证与版本"),
        ("huggingface_forum", "site:discuss.huggingface.co", "(error OR workaround OR solution)", "(报错 OR 解决 OR 讨论)", "查找 Hugging Face 官方论坛的复现与路线"),
        ("zhihu", "site:zhihu.com", "(implementation OR solution)", "(原理 OR 解决 OR 复现)", "发现线索并追溯原始论文或代码"),
        ("xiaohongshu", "site:xiaohongshu.com", "(solution OR experience)", "(经验 OR 踩坑 OR 解决)", "发现经验线索；受限页面应记录不可访问"),
        ("openreview", "site:openreview.net", "(method OR ablation OR reproducibility)", "(方法 OR 消融 OR 复现)", "核对会议、评审与论文版本"),
        ("pmlr", "site:proceedings.mlr.press", "(method OR implementation)", "(方法 OR 实现)", "查找机器学习会议原始论文"),
        ("cvf", "site:openaccess.thecvf.com", "(method OR implementation)", "(方法 OR 实现)", "查找视觉会议原始论文"),
        ("acl", "site:aclanthology.org", "(method OR evaluation)", "(方法 OR 评估)", "查找语言处理会议原始论文"),
        ("journals", "(site:nature.com OR site:science.org OR site:pnas.org)", "(method OR limitation)", "(方法 OR 局限)", "按实际学科补充期刊；名望不替代适用性判断"),
        ("scholars", '(author OR researcher OR "Google Scholar")', "(paper OR code)", "(学者 OR 论文 OR 代码)", "发现作者后查其主页、原论文与官方代码"),
        ("labs", '(laboratory OR lab OR "research group")', "(publication OR code OR benchmark)", "(实验室 OR 课题组 OR 开源)", "查实验室项目与可复现实验，不将机构名望当证据"),
    )
    source_details = {source: (site, english, chinese, purpose) for source, site, english, chinese, purpose in sources}
    queries = []
    for source in source_filters:
        site, english, chinese, purpose = source_details[source]
        if repository is not None and source in {"github_issues", "github_prs"}:
            section = "issues" if source == "github_issues" else "pull"
            site = f"site:github.com/{repository}/{section}"
        exact_error = source in {"github_issues", "github_prs", "huggingface", "huggingface_forum", "zhihu", "xiaohongshu"}
        base = precise if exact_error else mechanism
        for language in language_filters:
            terms = english if language == "en" else chinese
            queries.append({"id": f"S{len(queries) + 1}", "source": source,
                            "language": language, "query": f"{site} {base} {terms}",
                            "purpose": purpose, "stage": "error_match" if exact_error else "mechanism",
                            "note": "候选查询：优先核对报错与版本。" if exact_error else mechanism_note})
    total_candidates = len(queries)
    if max_queries is not None:
        queries = queries[:max_queries]
    return {"notice": NOTICE, "review_required": True,
            "note": "以下全部是候选计划；请按相关性优先选择 4–8 条并改写，不要求全部执行。数量上限仅控制生成，不是实际联网预算。",
            "total_candidates": total_candidates, "truncated": len(queries) < total_candidates, "queries": queries}


def new_case():
    return {
        "schema_version": 1,
        "case_id": "CASE-001",
        "problem": {
            "summary": "", "component": "", "versions": {}, "symptoms": [],
            "reproduction": {"command": "", "expected": "", "observed": "",
                             "exit_code": None, "status": "not_run"},
            "constraints": [],
        },
        "searches": [],
        "evidence": [],
        "mapping": [],
        "experiments": [],
        "validation": {"status": "blocked", "summary": "尚未复现和验证。",
                       "runs": [], "limitations": []},
    }


class CaseValidator:
    """检查所填写的记录。检查通过不代表记录真实或问题确已修复。"""

    def __init__(self):
        self.errors = []
        self.ids = set()

    def error(self, path, message):
        self.errors.append(f"{path}: {message}")

    def obj(self, value, path):
        if not isinstance(value, dict):
            self.error(path, "必须是对象")
            return {}
        return value

    def string(self, obj, key, path, nonempty=False):
        value = obj.get(key)
        if not isinstance(value, str) or (nonempty and not value.strip()):
            self.error(f"{path}.{key}", "必须是字符串" + ("且不能为空" if nonempty else ""))
        return value

    def choice(self, obj, key, choices, path):
        value = obj.get(key)
        if not isinstance(value, str) or value not in choices:
            self.error(f"{path}.{key}", "不是允许的状态")
            return None
        return value

    def strings(self, obj, key, path):
        value = obj.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            self.error(f"{path}.{key}", "必须是字符串数组")
            return []
        return value

    def rows(self, obj, key, path):
        value = obj.get(key)
        if not isinstance(value, list):
            self.error(f"{path}.{key}", "必须是对象数组")
            return []
        return [(self.obj(row, f"{path}.{key}[{index}]"), f"{path}.{key}[{index}]")
                for index, row in enumerate(value)]

    def identify(self, rows):
        ids = set()
        for row, path in rows:
            identifier = self.string(row, "id", path, nonempty=True)
            if not isinstance(identifier, str):
                continue
            if identifier in self.ids:
                self.error(f"{path}.id", "ID 必须在案例内唯一")
            self.ids.add(identifier)
            ids.add(identifier)
        return ids

    def refs(self, row, key, valid_ids, path, nonempty=False):
        references = self.strings(row, key, path)
        if nonempty and not references:
            self.error(f"{path}.{key}", "至少需要一个支持引用")
        if len(set(references)) != len(references) or any(ref not in valid_ids for ref in references):
            self.error(f"{path}.{key}", "引用必须存在且不能重复")

    def execution(self, row, path, kind=None):
        self.string(row, "command", path)
        self.string(row, "observed", path)
        result = self.choice(row, "result", {"fail", "pass", "not_run"}, path)
        exit_code = row.get("exit_code")
        expected_exit_code = row.get("expected_exit_code", 0)
        if type(expected_exit_code) is not int:
            self.error(f"{path}.expected_exit_code", "必须是整数；省略时为 0")
        if "attempt_id" in row:
            self.string(row, "attempt_id", path, nonempty=True)
        if "comparison_context" in row:
            context = self.obj(row["comparison_context"], f"{path}.comparison_context")
            if not context or any(not isinstance(key, str) or not key.strip()
                                  or not isinstance(value, str) or not value.strip()
                                  for key, value in context.items()):
                self.error(f"{path}.comparison_context", "必须是非空的字符串键值对象，记录需保持不变的比较条件")
        if exit_code is not None and type(exit_code) is not int:
            self.error(f"{path}.exit_code", "必须是整数或 null")
        if result != "not_run" and result in {"fail", "pass"}:
            for key in ("command", "observed"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    self.error(f"{path}.{key}", "已执行记录必须填写")
            if type(exit_code) is not int:
                self.error(f"{path}.exit_code", "已执行记录必须有整数退出码")
            if result == "pass" and exit_code != expected_exit_code:
                self.error(f"{path}.exit_code", "通过记录的退出码必须等于 expected_exit_code（默认 0）")
            if kind in {"reproduction", "benchmark"}:
                self.string(row, "criteria", path, nonempty=True)
        elif result == "not_run" and exit_code is not None:
            self.error(f"{path}.exit_code", "未执行记录必须为 null")
        if "criteria" in row and not (result in {"fail", "pass"} and kind in {"reproduction", "benchmark"}):
            self.string(row, "criteria", path, nonempty=True)

    def validate(self, case):
        # A validator instance may check several cases; IDs and errors are case-local.
        self.errors = []
        self.ids = set()
        case = self.obj(case, "case")
        if type(case.get("schema_version")) is not int or case.get("schema_version") != 1:
            self.error("case.schema_version", "必须为整数 1")
        self.string(case, "case_id", "case", nonempty=True)
        problem = self.obj(case.get("problem"), "case.problem")
        for key in ("summary", "component"):
            self.string(problem, key, "case.problem")
        versions = self.obj(problem.get("versions"), "case.problem.versions")
        if any(not isinstance(value, str) for value in versions.values()):
            self.error("case.problem.versions", "版本值必须是字符串")
        for key in ("symptoms", "constraints"):
            self.strings(problem, key, "case.problem")
        reproduction = self.obj(problem.get("reproduction"), "case.problem.reproduction")
        for key in ("command", "expected", "observed"):
            self.string(reproduction, key, "case.problem.reproduction")
        self.choice(reproduction, "status", {"not_run", "fail", "pass"}, "case.problem.reproduction")
        self.execution({**reproduction, "result": reproduction.get("status")}, "case.problem.reproduction")
        if "check_id" in reproduction:
            self.string(reproduction, "check_id", "case.problem.reproduction", nonempty=True)

        searches = self.rows(case, "searches", "case")
        evidence = self.rows(case, "evidence", "case")
        mappings = self.rows(case, "mapping", "case")
        experiments = self.rows(case, "experiments", "case")
        validation = self.obj(case.get("validation"), "case.validation")
        runs = self.rows(validation, "runs", "case.validation")
        search_ids, evidence_ids, mapping_ids, _experiment_ids, _run_ids = [
            self.identify(rows) for rows in (searches, evidence, mappings, experiments, runs)
        ]

        for row, path in searches:
            search_status = self.choice(row, "status", {"planned", "completed", "searched", "blocked", "not_relevant", "unavailable", "access_blocked"}, path)
            self.string(row, "source", path, nonempty=True)
            query = self.string(row, "query", path, nonempty=search_status in {"planned", "completed", "searched"})
            self.string(row, "searched_at", path, nonempty=search_status in {"completed", "searched"})
            self.choice(row, "language", {"en", "zh", "other"}, path)
            if "reason" in row or (isinstance(query, str) and not query.strip()):
                self.string(row, "reason", path, nonempty=True)
            if isinstance(row.get("query"), str) and not safe_search_input([row["query"]]):
                self.error(f"{path}.query", "含可能的凭据或私有 URL，需人工脱敏")
            for url in self.strings(row, "result_urls", path):
                if not public_url(url):
                    self.error(f"{path}.result_urls", "必须是无凭据的公网 HTTP(S) URL")

        for row, path in evidence:
            for key in ("url", "title", "source", "claim", "relevance"):
                self.string(row, key, path, nonempty=True)
            if not public_url(row.get("url")):
                self.error(f"{path}.url", "必须是无凭据的公网 HTTP(S) URL")
            access_status = self.choice(row, "access_status", {"read", "snippet_only", "access_blocked", "unavailable",
                                                                "accessible", "partial", "inaccessible", "not_checked"}, path)
            self.choice(row, "publication_status", {"published", "preprint", "discussion", "unknown",
                                                   "submitted", "accepted", "not_applicable"}, path)
            self.choice(row, "primary_status", {"primary", "secondary", "unknown"}, path)
            self.string(row, "published_at", path)
            self.string(row, "accessed_at", path, nonempty=access_status in {"read", "accessible"})
            self.string(row, "revision", path)
            self.string(row, "author", path)
            outcome = self.choice(row, "outcome", {"solved_report", "viable_route", "lead"}, path)
            if access_status in {"snippet_only", "partial", "access_blocked", "unavailable", "inaccessible", "not_checked"} and outcome != "lead":
                self.error(f"{path}.outcome", "只见片段、未读或无法访问的来源只能记录为 lead，不能声称来源已解决或给出可行路线")
            self.strings(row, "limitations", path)
            self.refs(row, "search_ids", search_ids, path)

        for row, path in mappings:
            for key in ("local_path", "symbol", "similarities", "differences", "hypothesis"):
                self.string(row, key, path, nonempty=key != "symbol")
            basis = row.get("basis", "external")
            if not isinstance(basis, str) or basis not in {"local_code", "external", "mixed"}:
                self.error(f"{path}.basis", "必须是 local_code、external 或 mixed")
            self.refs(row, "evidence_ids", evidence_ids, path, nonempty=basis != "local_code")

        for row, path in experiments:
            for key in ("hypothesis", "change"):
                self.string(row, key, path, nonempty=True)
            commands = self.strings(row, "commands", path)
            self.choice(row, "status", {"planned", "supports", "rejects", "inconclusive"}, path)
            self.refs(row, "evidence_ids", evidence_ids, path)
            self.refs(row, "mapping_ids", mapping_ids, path, nonempty=True)
            if "attempt_id" in row:
                self.string(row, "attempt_id", path, nonempty=True)
            if row.get("status") != "planned" and (not commands or any(not command.strip() for command in commands)):
                self.error(f"{path}.commands", "已执行实验必须记录非空命令")

        status = self.choice(validation, "status", {"solved", "partial", "blocked"}, "case.validation")
        self.string(validation, "summary", "case.validation", nonempty=True)
        self.strings(validation, "limitations", "case.validation")
        for row, path in runs:
            self.string(row, "check_id", path, nonempty=True)
            self.choice(row, "phase", {"before", "after"}, path)
            kind = self.choice(row, "kind", {"reproduction", "test", "benchmark"}, path)
            self.execution(row, path, kind)
            self.refs(row, "evidence_ids", evidence_ids, path)

        after_runs = [row for row, _ in runs if row.get("phase") == "after"]
        final_attempt = validation.get("final_attempt_id")
        attempt_mode = "final_attempt_id" in validation or any("attempt_id" in row for row in after_runs)
        if "final_attempt_id" in validation:
            self.string(validation, "final_attempt_id", "case.validation", nonempty=True)
        if attempt_mode:
            for row, path in runs:
                if row.get("phase") == "after" and "attempt_id" not in row:
                    self.error(f"{path}.attempt_id", "使用修复轮次时每条 after 记录均须标记所属轮次")
            if status == "solved" and "final_attempt_id" not in validation:
                self.error("case.validation.final_attempt_id", "solved 必须明确选择最终验收轮次，不能按数组顺序推断")
            if "final_attempt_id" in validation and not any(row.get("attempt_id") == final_attempt for row in after_runs):
                self.error("case.validation.final_attempt_id", "必须引用包含 after 记录的已有轮次")
            active_after = [row for row in after_runs if row.get("attempt_id") == final_attempt]
        else:
            active_after = after_runs

        solution_ids = set()
        if "solution" in case:
            solution = self.obj(case["solution"], "case.solution")
            strategy = self.choice(solution, "strategy", {"single", "combined"}, "case.solution")
            for key in ("rationale", "compatibility"):
                self.string(solution, key, "case.solution", nonempty=True)
            self.strings(solution, "tradeoffs", "case.solution")
            components = self.rows(solution, "components", "case.solution")
            for row, path in components:
                mapping_id = self.string(row, "mapping_id", path, nonempty=True)
                for key in ("contribution", "adaptation"):
                    self.string(row, key, path, nonempty=True)
                if "omitted" in row:
                    self.string(row, "omitted", path)
                if isinstance(mapping_id, str):
                    if mapping_id not in mapping_ids or mapping_id in solution_ids:
                        self.error(f"{path}.mapping_id", "必须引用已有且不重复的本地映射")
                    solution_ids.add(mapping_id)
            if strategy == "single" and len(components) != 1:
                self.error("case.solution.components", "single 需要一个方案组件")
            if strategy == "combined" and len(solution_ids) < 2:
                self.error("case.solution.components", "combined 需要至少两个不同的本地映射")
            if "unresolved_conflicts" in solution:
                conflicts = self.strings(solution, "unresolved_conflicts", "case.solution")
                if status == "solved" and conflicts:
                    self.error("case.solution.unresolved_conflicts", "存在未解决的组合冲突，不能标为 solved")

        if status == "solved":
            if not isinstance(problem.get("summary"), str) or not problem["summary"].strip():
                self.error("case.problem.summary", "solved 必须描述已解决的问题")
            supporting_experiments = [row for row, _ in experiments if row.get("status") == "supports"
                                      and (not attempt_mode or row.get("attempt_id") == final_attempt)]
            if not mappings or not supporting_experiments:
                self.error("case.validation.status", "solved 必须有本地映射及支持假设的实验；使用轮次时支持实验须属于 final_attempt_id，本地推断须标为 local_code")
            before_rows = [row for row, _ in runs if row.get("phase") == "before"]

            def check_key(row):
                key = tuple(row.get(field) for field in ("check_id", "kind", "command"))
                return key if all(isinstance(value, str) for value in key) else None

            original = {check_key(row) for row in before_rows if row.get("result") == "fail"
                        and isinstance(row.get("kind"), str) and row["kind"] in {"reproduction", "benchmark"}}
            before = {check_key(row) for row in before_rows}
            after = {check_key(row) for row in active_after if row.get("result") == "pass"}
            for keys in (original, before, after):
                keys.discard(None)
            if not original or not original.issubset(after):
                self.error("case.validation.runs", "solved 需要每个原问题检查的修复前失败与修复后通过，check_id、kind、command 须一致，类型须为 reproduction 或 benchmark")
            if not before.issubset(after):
                self.error("case.validation.runs", "所有已记录的 before 检查（含相关回归）均须有最终 after 通过记录")
            if any(row.get("result") != "pass" for row in active_after):
                self.error("case.validation.runs", "最终验收轮存在修复后失败或未执行项，不能标为 solved")
            for key in before.intersection(after):
                paired = [row for row in before_rows + active_after if check_key(row) == key]
                for field, default in (("criteria", None), ("expected_exit_code", 0), ("comparison_context", None)):
                    values = [row.get(field, default) for row in paired]
                    if any(value != values[0] for value in values):
                        self.error(f"case.validation.runs.{field}", "同一检查前后的通过标准、预期退出码和声明的比较条件必须一致")
            if reproduction.get("status") == "fail":
                matching = [row for row in before_rows if check_key(row) in original
                            and row.get("command") == reproduction.get("command")
                            and ("check_id" not in reproduction or row.get("check_id") == reproduction.get("check_id"))]
                if not matching:
                    self.error("case.problem.reproduction", "已记录的原始失败必须关联到 validation.runs 中同命令的 before 原症状检查；可用 check_id 明确关联")
                elif not any(all(field not in reproduction or reproduction[field] == row.get(field, default)
                                 for field, default in (("criteria", None), ("expected_exit_code", 0), ("comparison_context", None)))
                             for row in matching):
                    self.error("case.problem.reproduction", "原始失败中明确声明的标准、预期退出码和比较条件必须与关联的 before 检查一致")
            if "solution" in case:
                def covers_solution(row):
                    refs = row.get("mapping_ids")
                    return isinstance(refs, list) and all(isinstance(ref, str) for ref in refs) and solution_ids.issubset(set(refs))
                if not solution_ids or not any(covers_solution(row) for row in supporting_experiments):
                    self.error("case.solution.components", "solved 需要一个最终 supports 实验覆盖全部采用组件，不能以单独成功代替组合验证")
        return self.errors


def validate_case(case):
    return CaseValidator().validate(case)


VALIDATION_NOTICE = "仅检查所填写的记录和引用一致性，不独立证明问题已修复；不联网、不执行命令、不认证结果。"


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON 存在重复字段")
        result[key] = value
    return result


def reject_json_constant(_value):
    raise ValueError("JSON 不能包含非有限数值")


def emit_validation(errors, output_format, input_error=False):
    if output_format == "json":
        print(json.dumps({"valid": not errors, "scope": "record_consistency", "errors": errors,
                          "input_error": input_error, "notice": VALIDATION_NOTICE}, ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(error, file=sys.stderr)
    else:
        print("结构检查通过；" + VALIDATION_NOTICE)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "参数无效；运行 --help 查看用法。为避免泄露输入，未回显参数。\n")


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    query_parser = commands.add_parser("queries", help="生成英文和中文检索计划，不执行搜索", description=NOTICE)
    query_parser.add_argument("--error", required=True, help="已脱敏的报错或症状")
    query_parser.add_argument("--component", default="", help="组件名")
    query_parser.add_argument("--version", default="", help="版本号")
    query_parser.add_argument("--concept", action="append", default=[], help="概念词，可重复")
    query_parser.add_argument("--source", action="append", choices=SOURCE_IDS, help="筛选候选来源，可重复；按首次指定的顺序生成，省略时列出全部来源")
    query_parser.add_argument("--language", action="append", choices=LANGUAGE_IDS, help="筛选查询语言，可重复；按首次指定的顺序生成，默认 en、zh")
    query_parser.add_argument("--limit", type=int, help="最多生成的候选查询数，须为正整数；不代表实际联网预算")
    query_parser.add_argument("--repo", help="公开仓库 owner/name；仅缩小 GitHub issues 和 pull request 查询路径，不检查仓库是否存在")
    query_parser.add_argument("--format", choices=("json", "markdown"), default="json")
    init_parser = commands.add_parser("init", help="创建 blocked 案例模板，不覆盖已有文件")
    init_parser.add_argument("--output", required=True, type=Path)
    validate_parser = commands.add_parser("validate", help="检查记录结构，不证明实际修复")
    validate_parser.add_argument("file", type=Path)
    validate_parser.add_argument("--format", choices=("text", "json"), default="text", help="文本诊断或供 CI 使用的 JSON 结果")
    args = parser.parse_args(argv)
    try:
        if args.command == "queries":
            plan = make_queries(args.error, args.component, args.version, args.concept, args.source,
                                args.language, args.limit, args.repo)
            if args.format == "json":
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print(f"# 人工复核检索计划\n\n{NOTICE}\n\n{plan['note']}\n")
                print(f"生成候选：{len(plan['queries'])} / {plan['total_candidates']}；"
                      f"{'已按数量上限截断' if plan['truncated'] else '未截断'}。\n")
                for query in plan["queries"]:
                    print(f"- {query['id']} / {query['stage']} / {query['source']} / {query['language']}: {query['query']}\n  目的：{query['purpose']}\n  复核：{query['note']}")
        elif args.command == "init":
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(new_case(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print("已创建案例模板；初始状态为 blocked。")
        else:
            with args.file.open(encoding="utf-8") as handle:
                case = json.load(handle, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
            errors = validate_case(case)
            emit_validation(errors, args.format)
            return 1 if errors else 0
        return 0
    except (ValueError, RecursionError):
        if args.command == "validate":
            emit_validation(["案例 JSON 格式、编码或嵌套层级无效；未回显内容。"], args.format, input_error=True)
        else:
            print("查询参数无效、描述为空或含可能的凭据、非公开地址；请检查参数并脱敏。" + NOTICE, file=sys.stderr)
        return 2
    except FileExistsError:
        print("目标文件已存在；init 不覆盖已有内容。未回显路径。", file=sys.stderr)
        return 2
    except OSError:
        message = "文件操作失败；请检查输入文件、目录和权限。未回显路径。"
        if args.command == "validate":
            emit_validation([message], args.format, input_error=True)
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
