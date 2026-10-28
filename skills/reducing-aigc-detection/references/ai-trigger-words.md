# AI 特征词黑名单 (2025-2026)

> 来源：知网特征词库、Science 454词报告、维普实测、社区横评

## 中文高频触发词

### 过渡衔接类（最高危）

| 触发词 | 替换策略 |
|--------|---------|
| 首先…其次…最后/再次 | 删除序号词直接陈述；或用"一是…二是…"；或只保留最重要的一个展开 |
| 值得注意的是 | 删除，直接说注意什么 |
| 综上所述 | 删除或改为具体总结句 |
| 不可否认 | 删除 |
| 与此同时 | 改为"另一边" / "同一时期" / 直接并列不用连接 |
| 此外 / 另外 | 删除或改为"还有一点" |
| 一方面…另一方面 | 打碎为独立句子 |
| 不仅…而且/还 | 改为两个独立短句 |
| 总之 / 总而言之 | 删除，直接给结论 |
| 然而 / 但是（段首） | 偶尔保留，但不能每段都用 |

### 学术套话类

| 触发词 | 替换策略 |
|--------|---------|
| 研究表明/研究发现 | 引具体作者+年份+样本量：「张三（2024）在对500名受试者的调查中发现」 |
| 结果显示 | 给具体数字：「实验组平均得分提升12.3%」 |
| 具有重要意义/发挥着重要作用 | 说清楚重要在哪里，删掉空泛形容 |
| 主要体现在N个方面 | 最危险的模板之一。打碎为不均匀的叙述 |
| 在…方面 / 在…层面 | 改为"从…来看" / "说到…" / 直接切入 |
| 旨在 / 致力于 | 改为"想做的是" / "目标是" |
| 鉴于此 / 基于此 | 删除或改为"所以" |

### 结构模板类

| 模板 | 替换策略 |
|------|---------|
| 背景→问题→方法→结论 | 打乱顺序：先抛核心发现，再补背景 |
| 本文从A、B、C三个方面 | 不预告结构，直接展开 |
| 第一章…第二章…第三章… | 摘要中不逐章描述，合并为整体概述 |

## 英文高频触发词

### Science 报告标记的454词中最危险的

| Word/Phrase | Replacement Strategy |
|-------------|---------------------|
| delve(s) / delving | explore, examine, look at |
| furthermore / moreover | drop, or use "also" / "and" |
| it is important to note that | delete, state the fact directly |
| comprehensive | delete or be specific about scope |
| multifaceted / nuanced | delete |
| landscape (non-literal) | delete or be specific |
| underscores | shows, highlights |
| in conclusion | cut or rephrase |
| this report hopes to provide | delete; end with a concrete statement |
| integrates...with | combine, join, blend |
| The X section explains/introduces/presents | NEVER use 4+ parallel section descriptions |

### 英文结构模板

| Pattern | Fix |
|---------|-----|
| "This paper is organized as follows: Section 2... Section 3... Section 4..." | Merge description, vary verbs, skip minor sections |
| Uniform sentence length (15-25 words) | Mix 5-word and 35-word sentences deliberately |
| Every paragraph: topic sentence → 3 points → wrap-up | Break the template, vary paragraph structure |

## 检测逃逸策略

### 提升 Perplexity 的方法

- 使用低频同义词（偶尔）
- 插入学科特异性术语/行话
- 加入具体人名、地名、机构名
- 使用非最优但可接受的措辞

### 提升 Burstiness 的方法

- 穿插极短句（<8字）和长复杂句（>30字）
- 在段落中嵌入括号补充、破折号插入语
- 制造论证深度不均匀
- 加入自我修正：「最初以为…后来发现…」
- 偶尔使用反问句或感叹

### 注入人类指纹

- 个人经历/观察细节
- 对先行研究的具体（非泛泛的）评论
- 思维跳跃：未完全展开的暗示、交叉引用
- 轻微的不完美：偶尔重复、稍显冗余的澄清
- 口语化碎片（学术论文中可接受的程度）
