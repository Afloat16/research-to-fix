# 来源检索指南

按问题选择来源，记录每类是否已检索、无关、访问受限或工具不可用。先本地取问题指纹，再发送脱敏的最少公开词。以下模板需要替换占位符并按环境工具语法适配；GitHub 原生查询与联网搜索的 `site:` 查询不能混用。

## GitHub：从症状找到真正的修复

原生查询：

```text
repo:OWNER/REPO is:issue "ERROR_FRAGMENT"
repo:OWNER/REPO is:closed reason:completed linked:pr "SYMBOL"
repo:OWNER/REPO is:pr is:merged "SYMBOL"
```

联网搜索：

```text
site:github.com/OWNER/REPO/issues "ERROR_FRAGMENT" "VERSION"
site:github.com/OWNER/REPO/pull "SYMBOL" fix
```

精确错误无结果时拆掉动态路径/数字，搜索关键符号和机制，例如 dtype mismatch、rank divergence、iterator exhaustion。检索 open、duplicate、失败的方案及新版本回归，避免只看成功结果。不同连接器可能不接受原生过滤器；遵守其说明，必要时用 web search 或原站 API。

打开 issue 讨论、关联 PR、diff 和测试，核对修复 commit。确认所用 release/tag 包含修复，不能把关闭或合并时间当发行时间。commit 搜索仅覆盖默认分支，无结果不代表其他分支没有修复。

官方文档：[issue/PR 搜索](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/filtering-and-searching-issues-and-pull-requests)、[关联 issue 与 PR](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)、[commit 搜索](https://docs.github.com/en/search-github/searching-on-github/searching-commits)。

## Hugging Face：模型配置与工程条件

```text
site:huggingface.co "MODEL_OR_LIBRARY" "ERROR_FRAGMENT"
site:huggingface.co "MODEL" "dtype" "revision"
site:discuss.huggingface.co "ERROR_FRAGMENT"
```

分别查看 Hub 全文检索（cards/Spaces 等）、目标仓库 Community、官方文档与原作者 GitHub。核对模型/数据仓库归属和固定 revision、config/tokenizer、库版本、精度、硬件、数据许可、评估限制及解决反馈。HF 托管并不自动代表平台背书。阅读模型仓库的远程代码，不默认打开 `trust_remote_code`。

官方文档：[Hub 搜索](https://huggingface.co/docs/hub/en/search)、[Model Cards](https://huggingface.co/docs/hub/model-cards)、[Discussions/PR](https://huggingface.co/docs/hub/repositories-pull-requests-discussions)、[Community API](https://huggingface.co/docs/huggingface_hub/main/package_reference/community)。

## 知乎、小红书：经验与关键词线索

```text
site:zhihu.com "框架" "报错片段"
site:zhihu.com "症状" "版本" 解决
site:xiaohongshu.com "框架" "现象" 排坑
site:xiaohongshu.com "机制关键词" 复现
```

用简体中文术语、英文 API 名与同义词交叉检索。公开索引覆盖不完整；无结果不代表没有帖子。打开可访问正文，记录日期、作者和环境，沿链接追溯原始代码/论文/官方文档。只看标题、截图或搜索摘要时标为未经核验的线索，不据此修改关键代码。登录墙、删除页、403 或限流需具体记录；优先转公开原始材料，不假装读过内容。

## 顶刊顶会：按领域选择，不以名气代替匹配

| 领域/问题 | 常用原始入口 | 核验点 |
| --- | --- | --- |
| 机器学习 | [OpenReview](https://openreview.net/)、[PMLR](https://proceedings.mlr.press/)、[NeurIPS Proceedings](https://proceedings.neurips.cc/) | venue、年份、decision、main/workshop、官方实现 |
| 计算机视觉 | [CVF Open Access](https://openaccess.thecvf.com/) | 会议/track、附录、数据集、实现、适用任务 |
| 自然语言处理 | [ACL Anthology](https://aclanthology.org/) | proceedings/Findings/workshop、题名、版本、评测设置 |
| 系统/软件工程 | [USENIX](https://www.usenix.org/publications/proceedings)、[ACM DL](https://dl.acm.org/)、[IEEE Xplore](https://ieeexplore.ieee.org/) | 正式出版页、环境、工作负载、实现/复现材料 |
| 跨领域科研 | 相应期刊出版商、[arXiv](https://arxiv.org/)、DOI 原始页面 | 文章类型、发表状态、假设、勘误/撤稿、复现限制 |

从错误概念化为机制或任务，例如 numerical instability、distribution shift、memory fragmentation；用任务+机制+method/ablation/implementation 查询，再缩到官方入口。没有适用论文时明确缺口，不罗列无关“顶会”文章。

核对正式题名、作者、年份、venue、track、版本和发表状态。OpenReview 含投稿及不同活动，不是所有条目都已录用；PMLR 含主会与 workshop。arXiv 不提供同行评审，Journal-ref/DOI 需要在正式出处交叉确认；DOI 自身也不等于期刊论文。读实验和限制，确认原作者实现、依赖、数据切分、指标、seed 与资源条件。查看勘误与更新，付费正文不可达时仅基于公开摘要/作者稿说明范围。

官方说明：[arXiv 介绍](https://info.arxiv.org/about/index.html)、[Journal-ref/DOI 字段](https://info.arxiv.org/help/jref.html)、[OpenReview](https://openreview.net/about)、[Crossmark 更新与撤回](https://www.crossref.org/services/crossmark/)。

## 学者、实验室：身份确认后查原始路线

从论文作者页或机构目录找到正确的人与实验室，核对同名、机构和论文交叉链接，再检索：

```text
"AUTHOR_NAME" "MECHANISM" implementation
"LAB_NAME" "TASK" code technical report
site:VERIFIED_LAB_DOMAIN "MECHANISM"
```

优先原作者项目页、技术报告、教程、复现代码；记录日期和实现版本。知名学者、实验室和高引用数可帮助发现资料，不能自动提高一个不匹配方案的可信度。不要未经指示给作者发送邮件、issue 或私信。

## 搜索记录与结束

记录 query、语言、来源类别、检索日期、命中 URL、访问状态和下一步。未命中、工具不可用与访问受限分别记录。连续两轮无新证据时换机制或转本地最小实验；已得到兼容的可证伪方案时开始验证。不要依靠平台数量代替问题解决。
