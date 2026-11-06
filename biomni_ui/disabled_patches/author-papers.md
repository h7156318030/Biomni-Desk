---
title: 按作者查论文（区分同名）
description: 查某位研究者发表的论文，并把同名的不同人按单位分开，输出带 PMID 的清单
category: 文献
when_to_use: 用户问“查某某的论文”“某某发表了什么”“某作者的文章”时；尤其是中文姓名（拼音）这类容易重名的情况
avoid: 只是查某个主题的文献（用“文献检索与要点总结”）；不要使用 query_scholar（依赖 Google Scholar，本机网络访问不了，会失败）
uses: biomni_ui.lit.author_papers, biomni_ui.lit.openalex_author_candidates
chain: 可接“文献检索与要点总结”做某个方向的综述
---
## 做法（直接用现成的函数，不要自己拼检索式）
1. 先看有没有可用来区分的信息：单位（如 Tsinghua）、ORCID、研究方向。用户没给就先照常检索，不要停下来追问。
2. 运行一段代码，输出会自动按“单位”分组、剔除同名污染：

```python
from biomni_ui.lit import author_papers, openalex_author_candidates
print(openalex_author_candidates("Fangyuan Hao", 5))   # 候选人：单位、论文数、ORCID、方向
print(author_papers("Fangyuan Hao", max_results=30))     # 可加 affiliation="Tsinghua" 或 orcid="0000-0002-6332-645X"
```

3. 中文姓名的顺序有歧义，函数会同时尝试“姓 名”和“名 姓”两种读法；名字要按用户给的拼写传入。
4. 读输出：
   - 如果论文来自多个单位，说明可能是**不同的人重名**。不要把它们合并成一个人的成果。
   - 把候选人（OpenAlex）和论文分组（PubMed）对应起来，说明“哪一组最可能是用户要找的人”以及依据（单位、论文数、方向）；不确定就如实说不确定，并请用户提供单位或 ORCID。

## 输出约定
- 先一句话说明：找到几位可能的同名作者、各自大致单位。
- 对最可能的那位，列表：年份、标题、期刊、PMID（保持 `PMID: 数字` 的写法，方便核对来源）。
- 其他同名作者只用一行概述，不展开。
- 末尾写检索日期和检索式，并说明：只查了 PubMed 和 OpenAlex，不含未被收录的论文。

## 注意
- 函数打印的是工具实际返回的内容，答案里的 PMID 必须来自这些输出，不要补充记忆中的论文。
- 查不到就说查不到，列出已尝试的检索式。
