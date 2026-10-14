# 可复现案例：流式评估的两次遍历

这是用于验证工作流的小型合成项目，不能代表大型工程或科研任务的成功率。案例确实在本地完成了复现、联网查阅原始材料、修复、回归和内存测量；没有声称存在一条同版本的上游修复 issue。

## 症状与基线

原实现如下，对列表可用，对一次性 iterable 会耗尽输入；空输入也直接除零：

```python
def summarize(values):
    total = sum(values)
    count = sum(1 for _ in values)
    return {"count": count, "mean": total / count}
```

要求：列表与一次性 iterable 均返回 count/mean，空输入抛出含 empty 的 ValueError，大规模 float 流不能缓存全部元素，保留原有 `sum` 数值行为。

环境：Python 3.12.14 / Linux x86_64，访问原始资料日期：2026-10-13。

## 调研到本地映射

| 原始证据 | 来源结论 | 本地映射与限制 |
| --- | --- | --- |
| [Python iterator 定义](https://docs.python.org/3.12/glossary.html#term-iterator) | iterator 不能像容器一样重新开始遍历 | 第二次计数得到 0，直接对应 `summarize` 的调用顺序 |
| [Python sum](https://docs.python.org/3.12/library/functions.html#sum) | Python 3.12 改善 float 求和精度 | 手工 `+=` 会改变本地既有浮点行为；保留内建 `sum` |
| [itertools.tee](https://docs.python.org/3.12/library/itertools.html#itertools.tee) | 两个分支不同步消费会需要缓存 | 先完成求和再计数的方案不满足输入规模下的内存约束 |

在线 3.12 文档显示 3.12.15，与本地 patch 版本不同；机制通过本地测试核验。GitHub 也进行了检索，精确 patch 源码页面不可达，未假装读过。HF、知乎、小红书、论文与学者/实验室对这个基础 iterator 故障标为 not_relevant。

选择单遍计数生成器：在 `sum` 消费元素时同步计数，不缓存输入；`count==0` 时显式抛 ValueError。这是结合文档和本地代码得出的修复，未冒充来源已解决案例。

## 验证

从仓库根目录运行：

```bash
python -m unittest discover -s examples/streaming-metrics -v
python examples/streaming-metrics/check_memory.py
```

| 检查 | 改动前 | 改动后 |
| --- | --- | --- |
| 原 3 项 unittest | 2 errors，退出 1 | 全通过 |
| 增加一次性遍历/空输入/浮点回归后的同套检查 | 6 tests，2 failures / 5 errors，退出 1 | 6 tests，OK，退出 0 |
| 10k / 100k / 1m float 流，各 3 次 tracemalloc | 未测量 | count/mean 正确，峰值 1056–1080 bytes（初次试用测量），退出 0 |

内存阈值是峰值 ≤16 KiB，各规模最大差异 ≤4 KiB；数值会因 Python 与环境不同而改变。tracemalloc 是此 float 输入和解释器下的辅助测量，不是所有数值类型的完整内存证明。代码使用固定数量的状态且不缓存元素。

最终状态为 solved，仅针对案例约定的行为与输入。原测试预期没有改写，新增测试检查了简单修复可能遗漏的兼容行为。
