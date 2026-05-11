# BRD Section 5.3 — Chi phí vận hành (revised v2)

> **Status:** Supporting reference. Canonical MVP scope/cost/payment model is now `docs/brd-vi.md` v2.7.1 + `docs/prd-vi.md` v1.4.0. Use this file for infra-rate assumptions, not final product/payment scope.
>
> Bản viết lại section 5.3 của Tiền Về Nơi Đâu BRD v1.0 với pricing chính xác sau khi check published rates trực tiếp từ Railway và Fly.io. Update v2 sửa estimate Railway từ $35-45 → $10-15 cho 100 users (estimate v1 over-pessimistic do assume provisioned utilization, thực tế Railway charge theo actual consumption).
>
> **Cập nhật:** 2026-05-05 (v2)

---

## 5.3. Chi phí vận hành ước tính

### 5.3.1. Pricing rate published (May 2026)

**Railway (Hobby plan, $5 minimum + $5 credits, pay actual usage nếu vượt):**

| Resource | Per-second rate | Per-month rate (730h) |
|----------|----------------|----------------------|
| Memory (actual RSS) | $0.00000386/GB/s | ~$10.14/GB/mo |
| CPU (actual usage) | $0.00000772/vCPU/s | ~$20.29/vCPU/mo |
| Volume | $0.00000006/GB/s | ~$0.16/GB/mo |
| Egress | $0.05/GB | per-use |

**Quan trọng:** Railway charge theo **actual consumption**, không phải provisioned limit. App set limit 1GB RAM nhưng dùng 300MB RSS → chỉ trả tiền cho 300MB.

**Fly.io (post-2024 changes, no free tier cho new accounts):**

| Resource | Cost |
|----------|------|
| shared-cpu-1x 256MB | $1.94/mo |
| shared-cpu-1x 512MB | $3.19/mo |
| shared-cpu-1x 1GB | $5.70/mo |
| Volume storage | $0.15/GB/mo |
| Managed Postgres Basic | $38/mo (đã tăng từ ~$10-15 trước 2024) |

**Hetzner Cloud (Singapore DC available từ 2024):**

| Spec | Cost |
|------|------|
| CPX11 (2 vCPU, 2GB RAM, 40GB SSD, 20TB traffic) | €4.59 (~$5)/mo |
| CPX21 (3 vCPU, 4GB RAM, 80GB SSD) | €7.55 (~$8)/mo |
| Backup snapshot | 20% phí VM |

### 5.3.2. So sánh hosting platform — 100 users

Workload giả định: bot Telegram + Postgres + scheduled jobs cho daily recap + SePay webhook receiver. Realistic actual consumption: 0.05-0.1 vCPU avg + 300-450MB RSS cho app, 0.02-0.05 vCPU + 200-350MB RSS cho Postgres.

| Platform | 10 users | 100 users | 500 users | Setup effort | VN latency |
|----------|----------|-----------|-----------|--------------|------------|
| **Railway Hobby** (recommend MVP) | $5-7 | **$10-15** | $30-50 | Thấp nhất (30 phút) | Trung bình (200-300ms) |
| **Hetzner Singapore DIY** | $5-7 | $7-10 | $10-15 | Cao (8-15h ban đầu) | Tốt (50-80ms) |
| **Fly.io DIY Postgres** | $7-10 | $13-18 | $25-35 | Trung bình | Tốt (Singapore edge) |
| **Fly.io managed Postgres** | $40-45 | $46-50 | $60-75 | Thấp | Tốt |
| **DigitalOcean managed (Singapore)** | $20-25 | $27-32 | $55-65 | Trung bình | Tốt nhất |
| **VN VPS (Tinohost/Bizfly)** | $4-6 | $5-8 | $10-15 | Cao | **Best (<30ms)** |

### 5.3.3. Breakdown chi tiết — Recommend platform: Railway Hobby

**App service (Python bot + webhook + scheduler) — actual consumption:**

| Component | Avg consumption @ 100 users | Cost/mo |
|-----------|---------------------------|---------|
| Memory RSS (Python + libs + connection pool) | 300-450MB | $3.04-4.56 |
| CPU (5-10% avg, bursty peak evening) | 0.05-0.1 vCPU | $1.01-2.03 |
| **App subtotal** | | **~$4-7** |

**Postgres service:**

| Component | Avg consumption @ 100 users | Cost/mo |
|-----------|---------------------------|---------|
| Memory RSS (Postgres baseline) | 200-350MB | $2.03-3.55 |
| CPU (queries rất nhẹ) | 0.02-0.05 vCPU | $0.40-1.01 |
| Volume (5GB) | 5GB | $0.80 |
| **Postgres subtotal** | | **~$3-5** |

**Egress (Telegram messages tiny):** ~1-2GB/mo × $0.05 = **~$0.10**

**Tổng resource consumption: $7-12/mo**. Áp Hobby plan ($5 minimum):

| Scenario | Resource usage | Total bill |
|----------|---------------|-----------|
| Tight (mọi thứ tối ưu) | $7 | **$7** |
| Realistic | $9-12 | **$9-12** |
| Loose (over-provision, nhiều log) | $15-20 | **$15-20** |

**Plus operational tooling:**

| Hạng mục | Cost/mo |
|----------|---------|
| Domain .com (amortized) | $1 |
| Backup ngoài (Backblaze B2, daily pg_dump) | $1 |
| Error monitoring (Sentry free tier) | $0 |
| Uptime monitoring (UptimeRobot free) | $0 |
| **Total operational** | **~$2** |

→ **Total cho 100 users trên Railway: $12-17/mo**

### 5.3.4. Cost projection theo scale (Railway Hobby)

| Hạng mục | 10 users | 100 users | 500 users |
|----------|----------|-----------|-----------|
| Railway resource usage (app + Postgres) | $5 (min) | $10-15 | $30-50 |
| Domain + SSL | $1 | $1 | $1 |
| Backup ngoài (B2) | $1 | $1 | $2 |
| **Tổng fixed cost** | **~$7** | **~$12-17** | **~$33-53** |
| + 20% buffer | $8 | $14-20 | $40-64 |
| + Phase 2 email parsing (nếu enable) | — | +$15 | +$25 |

### 5.3.5. Chi phí phát sinh khi enable Phase 2

| Feature | Cost/tháng thêm | Lưu ý |
|---------|----------------|-------|
| Email transaction parsing (inbound) | +$10-15 | Postmark Inbound $10 cho 10k email/mo, Mailgun $35 cho volume cao hơn |
| Multi-bank webhook routing | +$2-5 | Tăng Postgres connection + storage |
| CSV export | +$0-2 | Negligible |
| Messenger integration | +$0-5 | Webhook overhead nhỏ |

### 5.3.6. Variable cost không tính ở trên

- **Payment processing fees:** PayOS 1.5-2% per transaction, Stripe 3.4% + 30c per transaction. Đây là COGS, không phải fixed cost — tính khi tính LTV/margin.
- **Customer support time:** 100 users × 1-2 ticket/tháng × 10-15 phút = 15-50 giờ/tháng nếu solo founder. Cost cơ hội: ~5-15 triệu VND/tháng nếu tính theo billable rate.
- **Developer ops time (chỉ áp khi self-host Hetzner):** 8-15h setup ban đầu + 2-4h/tháng maintenance ≈ 4-7tr ban đầu + 1-2tr/tháng. **Railway = $0 ops time** — đây là lợi thế chính.

---

## 5.4. Break-even analysis (revised v2)

### 5.4.1. Break-even theo platform @ 100 users

Pricing Pro = $4/mo (sau pricing redesign). Free tier = 45 tx/tháng, 1 bank account.

| Platform @ 100 users | Fixed cost | Paying users cần (@$4) | % conversion break-even |
|---------------------|-----------|----------------------|------------------------|
| **Railway Hobby** | $15 | **4** | **4%** |
| Hetzner Singapore DIY | $10 | 3 | 3% |
| Fly.io DIY Postgres | $17 | 5 | 5% |
| DO Singapore managed | $32 | 8 | 8% |
| Fly.io managed | $46 | 12 | 12% |

→ **Railway @ 4% break-even conversion** là realistic và không cần aggressive Pro tier. Hetzner thấp hơn 1% nhưng tradeoff bằng 8-15h ops setup time.

### 5.4.2. Break-even theo scale (Railway)

| Scale | Cost/mo | Paying users cần (@$4 Pro) | % conversion |
|-------|---------|---------------------------|--------------|
| 10 users | $7 | 2 | 20% (beta phase, OK) |
| 50 users | $10 | 3 | 6% |
| 100 users | $15 | 4 | 4% |
| 200 users | $22 | 6 | 3% |
| 500 users | $40 | 10 | 2% |

**Insight:** Unit economics improve nhanh khi scale lên. Ở 500 users, chỉ cần 2% conversion là break-even. Valley of death 50-150 users là phase cần focus retention nhất.

### 5.4.3. Sensitivity tới pricing tier

So sánh Pro $4 vs $3 (giá BRD cũ):

| Scale @ Railway | Cost | $3 Pro: % conversion cần | $4 Pro: % conversion cần |
|----------------|------|------------------------|------------------------|
| 100 users | $15 | 5% | 4% |
| 500 users | $40 | 3% | 2% |

→ Pricing $4 (đã đề xuất ở section 5.1 revised) cho buffer 20-25% dễ thở hơn $3 ở mọi scale.

### 5.4.4. Sensitivity tới conversion mix (Pro vs Business tier)

Với pricing 3-tier (Free / Pro $4 / Business $9):

| Scale | Cost | Mix giả định | Revenue/mo | Net |
|-------|------|-------------|-----------|-----|
| 100 users | $15 | 10% Pro, 2% Business | $40 + $18 = $58 | **+$43** |
| 500 users | $40 | 12% Pro, 4% Business | $240 + $180 = $420 | **+$380** |

→ Profitable từ 100 users nếu hit conversion target. **Margin >70%** ở 500 users là healthy SaaS economics.

---

## 5.5. Recommend platform theo timeline

| Phase | Platform | Cost/mo | Lý do |
|-------|----------|---------|-------|
| **Tháng 1-3** (dev + 0-30 beta users) | Railway Hobby | $5-10 | Ship fast, không invest ops time. Cost burn $5-10/mo chấp nhận được trong validation phase |
| **Tháng 4-6** (30-100 users, beginning paying) | Railway Hobby | $10-15 | Chưa cần migrate, focus product + retention |
| **Tháng 7-12** (100-300 users, $50-150 MRR) | Railway Hobby (vẫn) | $15-25 | Vẫn cheaper-than-effort để migrate. Margin healthy ở $4 Pro |
| **Tháng 13+ (300+ users, $200+ MRR)** | **Migrate Hetzner Singapore** | $10-15 | Migration trigger: khi Railway bill > $25/mo ổn định 2 tháng. Saving 1 năm > setup time investment |

**Migration trigger cụ thể:**

- Railway monthly bill > $30 trong 2 tháng liên tiếp **OR**
- Latency complaint từ ≥3 paying users **OR**
- VN-specific feature cần private network (rare)

→ Lúc đó: setup Hetzner CPX21 ($8/mo) + migrate trong 1 tuần.

---

## 5.6. Tránh các bẫy chi phí phổ biến

| Bẫy | Cách tránh |
|------|-----------|
| Long-polling Telegram (CPU constant cao) | Dùng webhook thay long-poll → CPU usage giảm 5-10x |
| Heavy logging không filter | Set log level INFO, exclude debug. Log structure JSON for query, không string concat |
| Multiple replicas khi chưa cần | Single replica cho <500 users. Replica chỉ khi paying users phàn nàn |
| Postgres connection leak | Dùng connection pooler (pgbouncer trong cùng container hoặc Railway addon) |
| Egress spike khi user xem export hàng ngày | Cache CSV export 1h trong volume, regenerate khi data thay đổi |
| Volume size grow uncontrolled | Cron job archive transactions >12 tháng cho user Free, >24 tháng cho Pro |

---

## 5.7. Plan validate cost trong beta

Trước khi commit BRD numbers:

**Tuần 1 beta (5 users):**
- Deploy Railway Hobby
- Đo: actual memory RSS, CPU avg, egress
- Verify: Railway dashboard → Usage breakdown

**Tuần 2 beta (10 users):**
- Tăng load 2x, đo lại
- Extrapolate linear: nếu 10 users = $X, predict 100 users = ~10X (với caveat: scaling thường sub-linear cho Postgres queries)

**Decision point cuối tháng 1:**
- Nếu actual cost ≤ $15/mo @ 10-20 users → numbers BRD valid, tiếp tục Railway
- Nếu actual cost > $25/mo @ 10-20 users → workload nặng hơn dự kiến, consider optimize hoặc migrate Hetzner sớm

---

## Caveat

- Pricing platform (đặc biệt Railway, Fly.io) thay đổi định kỳ — Fly.io đã thay đổi đáng kể trong 2024 (xóa free tier, tăng managed Postgres giá $38). Verify lại pricing trước commit hợp đồng dài hạn.
- Workload assumption (50 tx/user/tháng, daily recap, light queries) cần validate trong 2 tuần beta đầu. Nếu actual usage cao hơn 2x → revise cost projection.
- Numbers Railway dựa trên **actual usage billing model**. Real-world variance ±30% là bình thường. Hobby plan $5 minimum bảo vệ downside.
- Chi phí ngầm (developer time, customer support, marketing) **không** tính ở đây. Đây chỉ là infrastructure cost.
- Migration path Railway → Hetzner phải được architect từ đầu: dùng Docker Compose, env-var config, không Railway-specific buildpack. Tốn 30 phút setup ban đầu, save 1 tuần migration sau này.

---

**End of revised section v2.**
