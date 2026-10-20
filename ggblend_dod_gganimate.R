# =============================================================================
# ggblend + gganimate 範例：DoD 沖淤點雲與河道粒徑分布的過度重疊處理
# 資料為模擬資料，僅供示範；實際使用時請將「1. 模擬資料」區段替換為
# 你自己的 DoD 取樣點（例如由 terra::spatSample() 或 UAV 點雲抽出）與粒徑成果。
# =============================================================================

# install.packages(c("ggplot2", "ggblend", "gganimate", "dplyr", "tidyr",
#                    "gifski", "ragg", "svglite"))
library(ggplot2)
library(ggblend)
library(gganimate)
library(dplyr)
library(tidyr)

set.seed(114)

# ---- 1. 模擬資料 ------------------------------------------------------------

events <- c("蘇力(2013)", "潭美(2013)", "颱風事件 C", "颱風事件 D")
zones  <- c("上游河段", "中游河段", "下游河段")

## 1-1 DoD 取樣點：每個事件 × 河段各 4000 點
##     dz(m) = 高程變化；坡度越大越傾向沖刷，下游偏淤積；事件越大，變化幅度越大
dod <- expand_grid(event = factor(events, levels = events),
                   zone  = factor(zones,  levels = zones)) |>
  mutate(n = 4000) |>
  uncount(n) |>
  mutate(
    slope    = pmin(pmax(rnorm(n(), mean = c(25, 12, 5)[as.integer(zone)], sd = 6), 0), 60),
    strength = c(0.6, 1.0, 1.5, 0.8)[as.integer(event)],
    bias     = c(-0.4, 0.0, 0.5)[as.integer(zone)],
    dz       = (bias - 0.03 * (slope - 15)) * strength + rnorm(n(), 0, 0.35 * strength),
    area     = runif(n(), 0.5, 4)             # 以像元代表面積（m2）當點大小
  )

## 1-2 河道粒徑：各事件前後、各河段取 150 顆（模擬 D50 以 mm 計）
grain <- expand_grid(event = factor(events, levels = events),
                     zone  = factor(zones,  levels = zones)) |>
  mutate(n = 150) |>
  uncount(n) |>
  mutate(
    x_dist = runif(n(), 0, 1000),              # 距河口距離 (m)
    d50    = rlnorm(n(),
                    meanlog = log(c(180, 80, 25)[as.integer(zone)]) -
                              0.1 * as.integer(event),
                    sdlog = 0.5)
  )

# ---- 2. 靜態圖：ggblend 處理過度重疊 ----------------------------------------
## 概念：partition() 依河段分組，各組內部先合成，再用 multiply 與其他組相乘，
##       重疊越多、顏色越深，可看出點的集中位置。

pal <- c("上游河段" = "#d95f02", "中游河段" = "#1b9e77", "下游河段" = "#7570b3")

p_static <- dod |>
  filter(event == events[3]) |>
  ggplot(aes(x = slope, y = dz, color = zone, size = area)) +
  (geom_point(alpha = 0.6) |> partition(vars(zone)) |> blend("multiply")) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "grey30") +
  scale_color_manual(values = pal, name = "河段") +
  scale_size_continuous(range = c(0.6, 3), guide = "none") +
  labs(title = "DoD 高程變化 vs. 坡度（ggblend, multiply）",
       x = "坡度 (°)", y = "高程變化 dz (m)；正值=淤積、負值=沖刷") +
  theme_minimal(base_family = "sans") +
  theme(legend.position = "top")

## ggblend 需使用支援 group / blend mode 的繪圖裝置（Cairo 系列、pdf 等）。
## 若在 RStudio 預設裝置看不到混色效果，請直接存檔後檢視：
ggsave("dod_static_blend.png", p_static, width = 7, height = 5, dpi = 200,
       device = grDevices::png, type = "cairo")

# ---- 3. 動畫 A：DoD（坡度-高程變化）隨颱風事件變化 --------------------------

p_dod_anim <- dod |>
  ggplot(aes(x = slope, y = dz, color = zone, size = area)) +
  (geom_point(alpha = 0.6) |> partition(vars(zone)) |> blend("multiply")) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "grey30") +
  scale_color_manual(values = pal, name = "河段") +
  scale_size_continuous(range = c(0.6, 3), guide = "none") +
  coord_cartesian(ylim = c(-3, 3)) +
  labs(title = "DoD 沖淤特性：{closest_state}",
       x = "坡度 (°)", y = "高程變化 dz (m)") +
  theme_minimal(base_family = "sans") +
  theme(legend.position = "top") +
  transition_states(event, transition_length = 2, state_length = 1) +
  ease_aes("cubic-in-out")

## 混合模式需 Cairo 裝置；animate() 會把 ... 傳給裝置函式
anim_dod <- animate(p_dod_anim,
                    nframes = 80, fps = 10, width = 800, height = 560,
                    device = "png", type = "cairo",
                    renderer = gifski_renderer())
anim_save("dod_blend_anim.gif", anim_dod)

# ---- 4. 動畫 B：粒徑沿河道分布（log 軸）隨事件變化 ---------------------------

p_grain_anim <- ggplot(grain, aes(x = x_dist, y = d50, color = zone)) +
  (geom_point(size = 2.2, alpha = 0.7) |> partition(vars(zone)) |> blend("multiply")) +
  scale_y_log10(breaks = c(1, 10, 100, 1000)) +
  scale_color_manual(values = pal, name = "河段") +
  labs(title = "河道粒徑 D50 沿程分布：{closest_state}",
       x = "距河口距離 (m)", y = "D50 (mm, log)") +
  theme_minimal(base_family = "sans") +
  theme(legend.position = "top") +
  transition_states(event, transition_length = 2, state_length = 1) +
  ease_aes("cubic-in-out")

anim_grain <- animate(p_grain_anim,
                      nframes = 80, fps = 10, width = 800, height = 560,
                      device = "png", type = "cairo",
                      renderer = gifski_renderer())
anim_save("grain_blend_anim.gif", anim_grain)

# ---- 5. 套用到真實資料的提示 ------------------------------------------------
## DoD：用 terra 讀入差分影像後取樣，欄位對應如下：
##   library(terra)
##   dz_r    <- rast("DoD.tif")
##   slope_r <- terrain(rast("DEM_pre.tif"), "slope", unit = "degrees")
##   pts <- spatSample(c(dz_r, slope_r), 20000, method = "random", na.rm = TRUE, as.df = TRUE)
##   names(pts) <- c("dz", "slope")
## 點數到百萬級時請先抽樣，或改用 geom_hex() / geom_bin2d() 彙整，避免混合運算過慢。
