# Nguồn tham khảo

Khảo sát thực hiện ngày **13/08/2026**.

## ⚠️ Ghi chú về phương pháp và giới hạn

**Giới hạn kỹ thuật:** môi trường chạy khảo sát này **chặn truy cập trực tiếp**
tới `linkedin.com`, `learn.microsoft.com`, `getphyllo.com`, `nubela.co`. Vì vậy
các trích dẫn tài liệu chính thức của LinkedIn đến từ **nguồn thứ cấp trích lại
nguyên văn**, không phải từ việc tôi đọc trực tiếp trang gốc.

➡️ **Khuyến nghị:** trước khi ra quyết định có ràng buộc hợp đồng hoặc chi tiền,
hãy tự mở các link đánh dấu 🔒 bên dưới để xác nhận.

**Xác minh chéo đã thực hiện:** tôi phát hiện nhiều blog SEO ghi **sai năm** vụ
Proxycurl (ghi 2026 thay vì 2025). Bản khảo sát này dùng mốc đã đối chiếu với
nguồn nêu **số hiệu vụ án gốc** (3:25-cv-00828).

**Độ tin cậy theo loại nguồn:**

| Loại | Độ tin cậy | Ví dụ |
|---|---|---|
| 🏛️ Cơ quan nhà nước / toà án | Cao nhất | CNIL, EDPB |
| ⚖️ Hãng luật phân tích án lệ | Cao | Morgan Lewis, Quinn Emanuel, Proskauer |
| 📰 Báo chí chuyên ngành | Khá | CNBC, Bloomberg Law, The Record |
| 🏢 Blog nhà cung cấp | **Thấp — có thiên vị** | Evaboot, PhantomBuster, Bright Data, Coresignal |

Các con số về **giá**, **coverage**, và đặc biệt là **"tỷ lệ block"** của công cụ
scraping hầu hết đến từ nhóm cuối — hãy coi là tham khảo, không phải sự thật đã
kiểm chứng.

---

## 1. Tài liệu chính thức LinkedIn / Microsoft

- 🔒 [Sales Navigator Application Platform (SNAP) Documentation](https://learn.microsoft.com/en-us/linkedin/sales/) — nguồn của câu *"We are not currently accepting new partners…"*
- 🔒 [Restricted Uses of LinkedIn Marketing APIs and Data](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-05)
- 🔒 [Additional Terms for the LinkedIn Marketing API Program](https://www.linkedin.com/legal/l/marketing-api-terms)
- 🔒 [Export Account and Lead Information from Sales Navigator](https://www.linkedin.com/help/sales-navigator/answer/a102031) — nguồn của câu *"We currently don't offer the option to export…"*
- 🔒 [Integration between Sales Navigator and your CRM – Overview](https://www.linkedin.com/help/sales-navigator/answer/a106005)
- 🔒 [Turn the Salesforce Sync for Sales Navigator On and Off](https://www.linkedin.com/help/sales-navigator/answer/a102030)
- 🔒 [Manage CRM Sync with Sales Navigator](https://www.linkedin.com/help/sales-navigator/answer/a107066)
- 🔒 [Commercial use limit | LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a564226)
- 🔒 [Leads and Accounts | Sales Navigator Help](https://www.linkedin.com/help/sales-navigator/topic/a43)
- 🔒 [LinkedIn Service Terms](https://www.linkedin.com/legal/l/service-terms)
- 🔒 [LinkedIn Data Processing Agreement](https://legal.linkedin.com/dpa)
- [Integrate LinkedIn Sales Navigator with Dynamics 365 Sales](https://learn.microsoft.com/en-us/dynamics365/sales/linkedin/integrate-sales-navigator)

---

## 2. Án lệ và phân tích pháp lý

### hiQ Labs v. LinkedIn
- ⚖️ [hiQ v. LinkedIn Wrapped Up: Web Scraping Lessons Learned — ZwillGen](https://www.zwillgen.com/alternative-data/hiq-v-linkedin-wrapped-up-web-scraping-lessons-learned/)
- ⚖️ [LinkedIn v. hiQ: Landmark Data Scraping Suit — Morgan Lewis](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators)
- ⚖️ [LinkedIn's Data Scraping Battle with hiQ Labs Ends with Proposed Judgment — Privacy World](https://www.privacyworld.blog/2022/12/linkedins-data-scraping-battle-with-hiq-labs-ends-with-proposed-judgment/)
- ⚖️ [Ninth Circuit Holds Data Scraping is Legal — California Lawyers Association](https://calawyers.org/privacy-law/ninth-circuit-holds-data-scraping-is-legal-in-hiq-v-linkedin/)
- ⚖️ [What Recent Rulings Say About the Legality of Data Scraping — Farella Braun + Martel](https://www.fbm.com/publications/what-recent-rulings-in-hiq-v-linkedin-and-other-cases-say-about-the-legality-of-data-scraping/)

### Meta / X v. Bright Data
- ⚖️ [Major Decision Affects Law of Scraping — Meta Platforms v. Bright Data (Farella Braun + Martel)](https://www.fbm.com/publications/major-decision-affects-law-of-scraping-and-online-data-collection-meta-platforms-v-bright-data/)
- ⚖️ [Client Alert: Meta v. Bright Data — Quinn Emanuel](https://www.quinnemanuel.com/the-firm/news-events/client-alert-meta-v-bright-data-significant-decision-for-web-scraping-industry/)
- ⚖️ [Proskauer Secures Dismissal of Scraping Claims Against Bright Data](https://www.proskauer.com/release/proskauer-secures-dismissal-of-scraping-claims-against-bright-data)
- 📰 [Elon Musk's X loses lawsuit against Bright Data over data scraping — CNBC](https://www.cnbc.com/2024/05/10/elon-musks-x-loses-lawsuit-against-bright-data-over-data-scraping.html)
- [Catching Up on the Scraping Battle Between X and Bright Data — Eric Goldman blog](https://blog.ericgoldman.org/archives/2025/01/catching-up-on-the-heavyweight-scraping-battle-between-x-and-bright-data-guest-blog-post.htm)

### LinkedIn v. Proxycurl và các vụ khác
- 📰 [LinkedIn Wins Legal Case Against Data Scrapers — Social Media Today](https://www.socialmediatoday.com/news/linkedin-wins-legal-case-data-scrapers-proxycurl/756101/)
- 🔒 [Proxycurl Shuts Down. Thank you. — Nubela (thông báo của chính Proxycurl)](https://nubela.co/blog/goodbye-proxycurl/)
- 🔒 [Is Scraping LinkedIn Legal in 2026? (I Was Sued by LinkedIn) — Nubela](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/)
- [The #1 LinkedIn Scraping Startup ProxyCurl Shuts Down — StartupHub.ai](https://www.startuphub.ai/ai-news/startup-news/2025/the-1-linkedin-scraping-startup-proxycurl-shuts-down)
- 📰 [LinkedIn sues software company allegedly scraping data from millions of profiles (ProAPIs) — The Record](https://therecord.media/linkedin-sues-data-scraping-company)
- 📰 [LinkedIn Battles Online Scrapers in Perpetual Struggle Over Data — Bloomberg Law](https://news.bloomberglaw.com/artificial-intelligence/linkedin-battles-online-scrapers-in-perpetual-struggle-over-data)
- [LinkedIn settles scraping lawsuit against Singapore-based firm — Staffing Industry Analysts](https://www.staffingindustry.com/news/global-daily-news/linkedin-settles-scraping-lawsuit-against-singapore-based-firm)

---

## 3. Xử phạt bảo vệ dữ liệu (GDPR)

- 🏛️ [Data scraping: KASPR fined €240,000 — CNIL (nguồn gốc)](https://www.cnil.fr/en/data-scraping-kaspr-fined-eu240000)
- 🏛️ [Data scraping: French SA fined KASPR €240 000 — European Data Protection Board](https://www.edpb.europa.eu/news/news/2025/data-scraping-french-supervisory-authority-fined-kaspr-eu240-000_en)
- 🏛️ [Closure of the order issued against KASPR — CNIL](https://www.cnil.fr/en/closure-order-issued-against-kaspr)
- ⚖️ [CNIL Fines KASPR €240,000 — Gerrish Legal](https://www.gerrishlegal.com/blog/cnil-fines-kaspr-240000-for-illegally-collecting-linkedin-users-contact-details)
- ⚖️ [KASPR sanctioned by the CNIL — Delsol Avocats](https://www.delsol-lawyers.com/KASPR-company-sanctioned-by-the-CNIL-for-collecting-contact-details-on-LinkedIn-of-users-who-had-chosen-to-limit-their-visibility)
- ⚖️ [Data extraction: the CNIL heavily sanctions KASPR — Squair Law](https://www.squairlaw.com/en/blog/data-extraction-the-cnil-heavily-sanctions-kaspr-)

---

## 4. 🇻🇳 Pháp luật Việt Nam về dữ liệu cá nhân

- ⚖️ [Vietnam's New Personal Data Protection Law: A Closer Look — Tilleke & Gibbins](https://www.tilleke.com/insights/vietnams-new-personal-data-protection-law-a-closer-look/)
- ⚖️ [Vietnam's data protection laws: The basics and beyond — Baker McKenzie](https://connectontech.bakermckenzie.com/vietnams-data-protection-laws-the-basics-and-beyond/)
- [Vietnam Law on Personal Data Protection: Overview — Vietnam Briefing](https://www.vietnam-briefing.com/news/vietnam-law-on-personal-data-protection-latest-developments-and-insights.html/)
- [Vietnam's Personal Data Protection Decree: A Quick Guide — Vietnam Briefing](https://www.vietnam-briefing.com/news/vietnams-personal-data-protection-decree-a-quick-guide.html/)
- [Data Protection Guide Vietnam — Multilaw](https://www.multilaw.com/Multilaw/Multilaw/Data_Protection_Laws_Guide/DataProtection_Guide_Vietnam.aspx)

---

## 5. GDPR và B2B scraping

- [The Legality of Scraping B2B Data from LinkedIn: Navigating GDPR — Marketscan](https://www.marketscan.co.uk/insights/the-legality-of-scraping-b2b-data-from-linkedin/)
- [Is Scraping LinkedIn for B2B Prospecting GDPR Legal? — Wonit](https://wonit.ai/questions/scrape-linkedin-b2b-prospecting-gdpr)
- [Legal Web Scraping for Business Intelligence in 2026 — AppFlow](https://appflow.solutions/en/blog/legal-web-scraping-business-2026)
- [Data Scraping Under Fire: Lessons from KASPR's €240K Fine — Lexology](https://www.lexology.com/library/detail.aspx?g=816e5076-be04-4b81-b7ad-66497c364b2d)

---

## 6. LinkedIn Sales Insights (khai tử)

- [Sunsetting LinkedIn Sales Insights — LeadGenius](https://www.leadgenius.com/resources/sunsetting-linkedin-sales-insights)
- [Navigating the Sunset of LinkedIn Sales Insights — LeadGenius](https://www.leadgenius.com/resources/navigating-the-sunset-of-linkedin-sales-insights-how-leadgenius-fills-the-gap)
- [LinkedIn Sales Solutions Focusing on AI — Michael Levy](https://www.linkedin.com/pulse/linkedin-sales-solutions-focusing-ai-michael-levy-ltqse)

---

## 7. 🏢 API và tình trạng truy cập (nguồn thứ cấp — thiên vị nhẹ)

- 🔒 [LinkedIn API Access in 2026: Tiers, Approval & Alternatives — Phyllo](https://www.getphyllo.com/post/linkedin-api-access-in-2026-partner-program-approval-timeline-alternatives)
- [LinkedIn API 2026: Access, Endpoints, Limits & Alternatives — ConnectSafely](https://connectsafely.ai/articles/linkedin-api-complete-guide-2026)
- [LinkedIn Sales Navigator API: What Exists, Who Can Use It — Linked API](https://linkedapi.io/guides/linkedin-sales-navigator-api)
- [LinkedIn Sales Navigator API: Access, Pricing & Best Alternatives — Lobstr](https://www.lobstr.io/blog/linkedin-sales-navigator-api)
- [LinkedIn Sales Navigator API Guide — Evaboot](https://evaboot.com/blog/linkedin-sales-navigator-api)
- [LinkedIn API Organization Lookup: Developer Guide — ConnectSafely](https://connectsafely.ai/articles/linkedin-api-organization-lookup-guide-2026)

---

## 8. 🏢 Sales Navigator: bộ lọc, giới hạn, export (nguồn thứ cấp)

- [LinkedIn Sales Navigator Search Filters: 2026 Guide — Evaboot](https://evaboot.com/blog/linkedin-sales-navigator-search-filters)
- [All 30+ LinkedIn Sales Navigator Filters Explained — Outx](https://www.outx.ai/blog/linkedin-sales-navigator-filter)
- [LinkedIn Sales Navigator Filters Explained + 9 Hacks — Skylead](https://skylead.io/blog/linkedin-sales-navigator-filters/)
- [How to Search for Companies on LinkedIn — Derrick](https://derrick-app.com/linkedin/sales-navigator/company-search)
- [How to Export More Than 2500 Results in Sales Navigator — Evaboot](https://evaboot.com/blog/see-more-2500-leads-linkedin-sales-navigator-search)
- [How Many Leads Can You Save in Sales Navigator? — ProntoHQ](https://www.prontohq.com/sales-navigator/how-many-leads-save)
- [Sales Navigator Alerts for Effective Sales Outreach — Skylead](https://skylead.io/blog/sales-navigator-alerts/)
- [How To Use LinkedIn Sales Navigator Saved Searches — Evaboot](https://evaboot.com/blog/linkedin-sales-navigator-saved-searches)
- [LinkedIn Limits in 2026 (Complete Breakdown) — LeadLoft](https://www.leadloft.com/blog/linkedin-limits)
- [What Is LinkedIn Sales Navigator Advanced Plus Plan? — Evaboot](https://evaboot.com/blog/linkedin-sales-navigator-advanced-plus)

---

## 9. 🏢 Nhà cung cấp dữ liệu (nguồn marketing — kiểm chứng lại)

- [Top 5 B2B Data Providers in 2026 — Coresignal](https://coresignal.com/blog/b2b-data-providers/)
- [Coresignal vs People Data Labs — Crustdata](https://crustdata.com/blog/coresignal-vs-peopledatalabs)
- [Top 4 Company Data Providers in 2026 — Coresignal](https://coresignal.com/company-data-providers/)
- [Apollo.io vs ZoomInfo — Explorium](https://www.explorium.ai/compare/apollo-vs-zoominfo/)
- [The Best Apollo.io Alternatives — Cognism](https://www.cognism.com/blog/apollo-competitors)
- [EMEA B2B Data: Why Cognism Beats ZoomInfo and Apollo.io — Cognism](https://www.cognism.com/blog/emea-b2b-data)
- [Top 3 Compliant Proxycurl Alternatives — Bright Data](https://brightdata.com/blog/web-data/proxycurl-alternatives)
- [Proxycurl Is Gone: Best LinkedIn Data API Alternatives — Linked API](https://linkedapi.io/guides/proxycurl-alternatives)
- [Proxycurl Review: Shutdown & Best Alternative — ZoomInfo](https://pipeline.zoominfo.com/sales/proxycurl-review)
- [Best B2B Data Providers for Prospecting in 2026 — Starnus](https://starnus.com/blog/best-b2b-data-providers-zoominfo-apollo-pdl)

---

## 10. 🏢 Công cụ scraping/automation (nguồn marketing — độ tin cậy thấp)

> ⚠️ Các bài dưới đây do chính nhà cung cấp công cụ hoặc đối thủ viết. Các tuyên
> bố kiểu *"zero ban risk"* hay *"block rate 12%"* **không có kiểm chứng độc lập**.

- [Does LinkedIn Ban You for Using Automation Tools? — PhantomBuster](https://phantombuster.com/blog/linkedin-automation/linkedin-ban-automation-tools/)
- [Why LinkedIn Flags Your Account for Automation — PhantomBuster](https://phantombuster.com/blog/social-selling/linkedin-automation-tool-warning/)
- [Why LinkedIn Bans Accounts Even When You Stay Under 'Safe Limits' — PhantomBuster](https://phantombuster.com/blog/linkedin-automation/linkedin-banned-even-under-safe-limits/)
- [LinkedIn Scraping Tools: Benchmarked by Block Rate and Ban Risk — Clura](https://clura.ai/blog/linkedin-scraping-tools)
- [12 Best LinkedIn Scraper Tools in 2026 — Cleverly](https://www.cleverly.co/blog/linkedin-scraper-tools)
- [10 LinkedIn Scraping Tools Tested + Compliance Risk — Cleanlist](https://www.cleanlist.ai/blog/2026-03-19-best-linkedin-scraping-tools)
- [Evaboot Pricing 2026: Real Cost — Derrick](https://derrick-app.com/tools/evaboot-pricing)
- [Evaboot Review — Pricing & Accuracy — SyncGTM](https://syncgtm.com/blog/evaboot-review)
- [Top 10 Evaboot Alternatives — Derrick](https://derrick-app.com/tools/evaboot-alternatives)
- [Best LinkedIn Scrapers in 2026 — Bright Data](https://brightdata.com/blog/web-data/best-linkedin-scraping-tools)
- [LinkedIn Commercial Use Limit — PhantomBuster](https://phantombuster.com/blog/social-selling/linkedin-commercial-use-limit/)

---

## 11. 🇻🇳 Nguồn dữ liệu doanh nghiệp Việt Nam

- [Vietnam Company Search Guide 2026 — BusinessDataGuide](https://www.businessdataguide.com/blog/jurisdictions/vietnam-company-search-guide)
- [Company Database Vietnam — 1,829,295 Legal Entities — CompanyData.com](https://companydata.com/database/vietnam/)
- [Vietnam B2B Data — 1.8M+ Verified Companies — InfobelPRO](https://www.infobelpro.com/b2b-data/vietnam)
- [Vietnam Company Search / KYB — AsiaVerify](https://asiaverify.com/know-your-business/kyb-vietnam/)
- [Verify Vietnamese Companies with Registry Data — AsiaVerify](https://asiaverify.com/resources/guides/how-to-verify-a-company-in-vietnam/)
- [Company Registry in Vietnam — Emerhub](https://emerhub.com/vietnam/company-registry-in-vietnam/)
- [Companies House Vietnam](https://companieshouse.vn/)

**Nguồn nhà nước (tra cứu trực tiếp):**
- Cổng thông tin đăng ký doanh nghiệp quốc gia: `dangkykinhdoanh.gov.vn`
- Hệ thống mạng đấu thầu quốc gia: `muasamcong.mpi.gov.vn`
