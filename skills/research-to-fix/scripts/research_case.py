#!/usr/bin/env python3
"""离线检索计划与证据案例检查；不会联网、上传或执行记录中的命令。"""

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


NOTICE = "仅供人工复核；敏感信息检测不是完整保证。工具不会联网、上传或执行搜索结果。"
SOURCE_IDS = ("github_issues", "github_prs", "huggingface", "huggingface_forum", "zhihu", "xiaohongshu",
              "openreview", "pmlr", "cvf", "acl", "journals", "scholars", "labs")
SECRET_PATTERNS = (
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    r"\b(?:hf_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{16,})",
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    r"(?i)\b(?:api[_ -]?key|access[_ -]?token|token|secret|password|pwd|authorization|bearer)[\"']?\s*[:=]\s*[\"']?\S+",
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{8,}",
    r"(?i)[?&](?:sig|x-amz-credential|x-amz-signature|x-amz-security-token|x-goog-signature)=\S+",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.I)
URI_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+")
PRIVATE_HOST_PATTERN = re.compile(
    r"(?i)\b(?:localhost|[a-z0-9-]+\.(?:local|internal|localhost|lan))(?::\d+)?(?:/|\b)"
)


def public_url(value):
    """只接受无凭据的公网 HTTP(S) URL；不发起 DNS 或网络请求。"""
    if not isinstance(value, str) or re.search(r"\s|[\\\x00-\x1f\x7f]", value):
        return False
    if any(re.search(pattern, value) for pattern in SECRET_PATTERNS):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None:
            return False
        if parsed.password is not None or parsed.port == 0:
            return False
        sensitive_keys = {"sig", "token", "api_key", "apikey", "access_token", "password",
                          "x-amz-credential", "x-amz-signature", "x-amz-security-token", "x-goog-signature"}
        if any(key.lower() in sensitive_keys for key, _value in parse_qsl(parsed.query, keep_blank_values=True)):
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
    """拒绝明显凭据或私有 URL；错误永远不含被拒绝的原文。"""
    for value in values:
        if any(re.search(pattern, value) for pattern in SECRET_PATTERNS):
            return False
        if PRIVATE_HOST_PATTERN.search(value):
            return False
        for uri in URI_PATTERN.finditer(value):
            try:
                parsed = urlsplit(uri.group(0))
                if parsed.username is not None or parsed.password is not None:
                    return False
            except ValueError:
                return False
        addresses = re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", value)
        addresses += re.findall(r"(?<!\w)(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*", value)
        for address in addresses:
            try:
                if not ipaddress.ip_address(address).is_global:
                    return False
            except ValueError:
                pass
        if any(not public_url(match.group(0)) for match in URL_PATTERN.finditer(value)):
            return False
    return True


def make_queries(error, component="", version="", concepts=None, source_filters=None):
    parts = [error, component, version, *(concepts or [])]
    if not safe_search_input(parts):
        raise ValueError("检测到可能的凭据或私有 URL，请脱敏后重试。" + NOTICE)
    if source_filters and any(source not in SOURCE_IDS for source in source_filters):
        raise ValueError("检索来源无效；请使用 --help 中列出的来源。")
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
    queries = []
    for source, site, english, chinese, purpose in sources:
        if source_filters and source not in source_filters:
            continue
        exact_error = source in {"github_issues", "github_prs", "huggingface", "huggingface_forum", "zhihu", "xiaohongshu"}
        base = precise if exact_error else mechanism
        for language, terms in (("en", english), ("zh", chinese)):
            queries.append({"id": f"S{len(queries) + 1}", "source": source,
                            "language": language, "query": f"{site} {base} {terms}",
                            "purpose": purpose, "stage": "error_match" if exact_error else "mechanism",
                            "note": "候选查询：优先核对报错与版本。" if exact_error else mechanism_note})
    return {"notice": NOTICE, "review_required": True,
            "note": "以下全部是候选计划；请按相关性优先选择 4–8 条并改写，不要求全部执行。", "queries": queries}


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
        if exit_code is not None and type(exit_code) is not int:
            self.error(f"{path}.exit_code", "必须是整数或 null")
        if result != "not_run" and result in {"fail", "pass"}:
            for key in ("command", "observed"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    self.error(f"{path}.{key}", "已执行记录必须填写")
            if type(exit_code) is not int:
                self.error(f"{path}.exit_code", "已执行记录必须有整数退出码")
            if result == "pass" and exit_code != 0:
                self.error(f"{path}.exit_code", "通过记录的退出码必须为 0")
            if kind in {"reproduction", "benchmark"}:
                self.string(row, "criteria", path, nonempty=True)
        elif result == "not_run" and exit_code is not None:
            self.error(f"{path}.exit_code", "未执行记录必须为 null")

    def validate(self, case):
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
            for key in ("query", "source"):
                self.string(row, key, path, nonempty=True)
            self.string(row, "searched_at", path)
            self.choice(row, "language", {"en", "zh", "other"}, path)
            self.choice(row, "status", {"planned", "completed", "blocked", "not_relevant", "unavailable", "access_blocked"}, path)
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

        if status == "solved":
            if not isinstance(problem.get("summary"), str) or not problem["summary"].strip():
                self.error("case.problem.summary", "solved 必须描述已解决的问题")
            if not mappings or not any(row.get("status") == "supports" for row, _ in experiments):
                self.error("case.validation.status", "solved 必须有本地映射及支持假设的实验；本地推断须明确标为 local_code")
            before = {(row.get("check_id"), row.get("kind"), row.get("command")) for row, _ in runs
                      if row.get("phase") == "before" and row.get("result") == "fail"
                      and isinstance(row.get("kind"), str) and row.get("kind") in {"reproduction", "benchmark"}
                      and isinstance(row.get("check_id"), str) and isinstance(row.get("command"), str)}
            after = {(row.get("check_id"), row.get("kind"), row.get("command")) for row, _ in runs
                     if row.get("phase") == "after" and row.get("result") == "pass"
                     and isinstance(row.get("check_id"), str) and isinstance(row.get("kind"), str)
                     and isinstance(row.get("command"), str)}
            if not before or not before.issubset(after):
                self.error("case.validation.runs", "solved 需要每个原问题检查的修复前失败与修复后通过，check_id、kind、command 须一致，类型须为 reproduction 或 benchmark")
            if any(row.get("phase") == "after" and row.get("result") != "pass" for row, _ in runs):
                self.error("case.validation.runs", "存在修复后失败或未执行项，不能标为 solved")
            for check_id, kind, command in before.intersection(after):
                criteria = [row.get("criteria") for row, _ in runs
                            if row.get("check_id") == check_id and row.get("kind") == kind and row.get("command") == command]
                if any(value != criteria[0] for value in criteria):
                    self.error("case.validation.runs", "原问题检查前后的通过标准必须一致")
        return self.errors


def validate_case(case):
    return CaseValidator().validate(case)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "参数无效；运行 --help 查看用法。为避免泄露输入，未回显参数。\n")


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    query_parser = commands.add_parser("queries", help="生成英文和中文检索计划，不执行搜索")
    query_parser.add_argument("--error", required=True, help="已脱敏的报错或症状")
    query_parser.add_argument("--component", default="", help="组件名")
    query_parser.add_argument("--version", default="", help="版本号")
    query_parser.add_argument("--concept", action="append", default=[], help="概念词，可重复")
    query_parser.add_argument("--source", action="append", choices=SOURCE_IDS, help="筛选候选来源，可重复；省略时列出全部来源")
    query_parser.add_argument("--format", choices=("json", "markdown"), default="json")
    init_parser = commands.add_parser("init", help="创建 blocked 案例模板，不覆盖已有文件")
    init_parser.add_argument("--output", required=True, type=Path)
    validate_parser = commands.add_parser("validate", help="检查记录结构，不证明实际修复")
    validate_parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "queries":
            plan = make_queries(args.error, args.component, args.version, args.concept, args.source)
            if args.format == "json":
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print(f"# 人工复核检索计划\n\n{NOTICE}\n\n{plan['note']}\n")
                for query in plan["queries"]:
                    print(f"- {query['id']} / {query['stage']} / {query['source']} / {query['language']}: {query['query']}\n  目的：{query['purpose']}\n  复核：{query['note']}")
        elif args.command == "init":
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(new_case(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print("已创建案例模板；初始状态为 blocked。")
        else:
            with args.file.open(encoding="utf-8") as handle:
                case = json.load(handle)
            errors = validate_case(case)
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print("结构检查通过；仅检查所填写的记录，不独立证明问题已修复。请人工核对原始证据、命令输出和剩余局限。")
        return 0
    except ValueError:
        # JSON 错误及脱敏错误均不得带出输入片段。
        print("输入无效或含可能的凭据、私有 URL；请检查 JSON 并脱敏后重试。" + NOTICE, file=sys.stderr)
        return 2
    except OSError:
        print("文件操作失败；请检查权限、文件是否存在及输出是否已被占用。未回显路径。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
