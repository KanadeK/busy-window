# busy-window 中文说明

从本地 `.ics` 文件导出指定日期范围内的忙碌时段。展开重复日程、处理排除日期和实例覆盖，
合并重叠或相邻区间，输出全新的 UTC `Busy` 事件。不会复制标题、正文、人员、链接、提醒、
原 UID 或扩展属性。处理过程不联网，也不需要日历账号。

需要 Python 3.11+。创建并激活虚拟环境后：

```console
python -m pip install .
python scripts/demo.py
busy-window examples/source.ics --from 2026-11-02 --to 2026-11-06 --timezone Asia/Shanghai --output busy.ics
```

起始日期包含、结束日期不包含，按 `--timezone` 的本地午夜确定。这个时区同时用于无时区
时间和全天事件；已经明确时区的事件保留真实时间点。透明和已取消事件忽略，暂定事件算忙碌。
输出路径必须不存在。可用 `--pad-minutes 5 --round-minutes 15` 向两侧扩展并向外取整，
之后裁剪到日期范围。退出码：成功 0，输入/处理/I/O 错误 2，中断 130。

默认限制为 8 MiB 输入、10,000 个组件、10,000 个展开实例、1–366 天范围，命令行子进程
最多运行 30 秒。只支持 VEVENT；不投影 VFREEBUSY/VTODO，暂不支持 RDATE PERIOD。
没有 UID/DTSTART 的事件、浮动时间的 DST 歧义、错误的重复规则等会失败，不写出部分日历。

忙碌时段本身仍可能暴露生活规律，不能保证匿名。每次导出会生成新 UID，反复追加导入可能
产生重复事件，应替换先前的导入。项目代码采用 MIT，部分独立运行时依赖采用 LGPL，详见
[THIRD_PARTY.md](THIRD_PARTY.md)。

卸载：`python -m pip uninstall busy-window`。虚拟环境是独立可清理的依赖目录。
完整语义、限制和测试命令见 [English README](README.md)。
