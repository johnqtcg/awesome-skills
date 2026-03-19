# Chinese Search Ecosystem

Google is the default, but significant Chinese-language content lives in walled gardens that Google cannot index well. Adapt the source path when the topic is China-centric or the user is searching in Chinese.

## When to go beyond Google

| Content Type | Where It Lives | How to Search |
| --- | --- | --- |
| WeChat articles (公众号) | WeChat ecosystem, not indexed by Google | Use 微信搜一搜 or Sogou |
| Baidu-exclusive content | Baidu Zhidao, Baidu Baike, Tieba | Search on baidu.com directly |
| Zhihu deep answers | Partially indexed by Google | `site:zhihu.com` on Google, or search Zhihu directly |
| Xiaohongshu (小红书) | Mostly app-only, limited web index | Search within the app, or `site:xiaohongshu.com` |
| Government notices (政务) | gov.cn domains | `site:gov.cn` on Google or Baidu |
| Baidu Netdisk resources | Baidu Pan | Use specialized netdisk search engines |

## Language Switching Strategy

For topics with global and local dimensions, search in both languages:

1. English first for global technology, open-source projects, RFCs, standards, academic papers, and vendor docs
2. Chinese first for China-specific policy, domestic companies, local regulations, and Chinese community discussions
3. Both, then merge for mixed topics such as engineering best practices

## Chinese Name Disambiguation

Chinese names have high collision rates. Always add disambiguators:

- `"张伟" "阿里巴巴"`
- `"张伟" "杭州"`
- `intext:"张伟" "数据库"`

Cross-reference at least two independent sources before concluding two records refer to the same person.

## Chinese-Specific Query Patterns

### Technical content (developer-focused)

- `"关键词" site:zhihu.com` — in-depth technical Q&A and discussions
- `"关键词" site:juejin.cn` — developer articles and tutorials
- `"关键词" site:segmentfault.com` — Chinese Stack Overflow equivalent
- `"关键词" site:cnblogs.com` — individual developer blogs
- `"关键词" (site:learnku.com OR site:studygolang.com)` — Go-specific Chinese community
- `"error message" "解决方案" OR "解决办法"` — Chinese troubleshooting articles
- `"关键词" 最佳实践 after:YYYY-MM-DD` — recent best-practice articles in Chinese
- `"关键词" 踩坑 OR 避坑` — real-world pitfall reports (often more candid than formal tutorials)

### Official and government sources

- `"关键词" site:gov.cn` — Chinese government notices and policies
- `"关键词" site:stats.gov.cn` — National Bureau of Statistics data
- `"关键词" site:mof.gov.cn` — Ministry of Finance policies
- `"公司名" site:cninfo.com.cn` — listed company filings and announcements
- `"关键词" filetype:pdf site:gov.cn` — government PDF reports

### Company and product research

- `"公司名" 融资 OR 估值` — funding and valuation info
- `"产品名" 测评 OR 评测 site:zhihu.com` — product reviews
- `"公司名" 裁员 OR 组织调整 after:YYYY-MM-DD` — org changes
- `"公司名" 技术栈 OR 架构` — company tech stack discussions

### Academic and research

- `"关键词" site:cnki.net` — CNKI (China National Knowledge Infrastructure) papers
- `"论文标题" filetype:pdf` — direct PDF search for Chinese papers
- `"关键词" site:wanfangdata.com.cn` — Wanfang academic database
- `"关键词" 综述 OR 研究进展 filetype:pdf` — survey papers and research reviews

### Platform-specific (not indexed by Google)

These require searching on the platform directly, not via Google:

| Platform | What to search | How |
| --- | --- | --- |
| WeChat (微信搜一搜) | 公众号 articles, mini-program content | Use WeChat app search or sogou.com WeChat tab |
| Xiaohongshu (小红书) | User experience reports, product comparisons | Search within the app |
| Douyin (抖音) | Video tutorials, visual demonstrations | Search within the app |
| Baidu Tieba (百度贴吧) | Niche community discussions | Search on tieba.baidu.com |
| Baidu Netdisk (百度网盘) | Shared file resources | Use specialized netdisk search engines |

Tactics:
- Always try Google first with `site:` constraints — some Chinese platform content is partially indexed
- If Google returns nothing, tell the user which platform to search directly and suggest keywords
- For technical topics, search both English and Chinese — English for official docs, Chinese for real-world experience reports from domestic teams

## Chinese Domain Quality Filtering

Chinese-language Google results are heavily polluted by SEO content farms that repost, translate, or auto-generate content. Actively filter these to avoid contaminating your evidence.

### Known Low-Quality Domains (Exclude by Default)

Add these `-site:` exclusions when Chinese search results are dominated by reposts:

```
-site:csdn.net -site:csdnimg.cn
-site:php.cn
-site:jb51.net
-site:w3cschool.cn
-site:itmag.cn -site:itcoder.net
-site:codenong.com
-site:cxybb.com
-site:haicoder.net
-site:codeleading.com
-site:programmerall.com
-site:shuzhiduo.com
-site:icode9.com
```

### Quick Exclusion Template

For technical Chinese searches, start with this base:

```
"关键词" -site:csdn.net -site:php.cn -site:jb51.net -site:w3cschool.cn (site:zhihu.com OR site:juejin.cn OR site:segmentfault.com)
```

### Content Farm Recognition Signs

If a source was not pre-excluded, check for these red flags before trusting:
- Article has no author name or profile
- Identical or near-identical content found on 3+ other domains
- Page is riddled with ads, auto-translated text, or keyword-stuffed headers
- Publication date is missing or obviously faked
- Code examples contain errors that a real developer would catch

When you find content-farm results, switch to positive `site:` targeting (zhihu.com, juejin.cn, official docs) instead of trying to blacklist every farm

### Language-switching query pairs

For topics with both global and local dimensions, prepare paired queries:

| English query | Chinese query | Why both |
| --- | --- | --- |
| `Go context best practices` | `Go context 最佳实践 踩坑` | English for official guidance, Chinese for real pitfalls |
| `MySQL connection pool tuning` | `MySQL 连接池 调优 生产环境` | English for vendor docs, Chinese for production war stories |
| `Kafka vs RocketMQ benchmark` | `Kafka RocketMQ 性能对比 实测` | English for global benchmarks, Chinese for domestic comparisons |
