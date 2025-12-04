# 地震事件資料交換格式 (Earthquake Event Message Format)

本文檔定義了地震事件資料的 JSON 訊息格式，用於系統間的資料交換與 WebUI 顯示。

## 📋 目錄

- [訊息類型](#訊息類型)
- [資料結構說明](#資料結構說明)

---

## 訊息類型

系統支援三種訊息類型：

| 訊息類型 | 說明 | 使用時機 |
|---------|------|---------|
| `add_event` | 新增地震事件 | 當偵測到新的地震事件時 |
| `update_location` | 更新位置資訊 | 當地震定位結果更新時 |
| `update_focal` | 更新震源機制解 | 當震源機制解計算完成時 |

---

## 資料結構說明

### 1. add_event - 新增地震事件

當系統偵測到新的地震事件時發送此訊息。

#### 欄位說明

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| `event_id` | integer | 地震事件的 index |
| `event_time` | string | 地震發生時間（例如：2024-04-09T12:06:22.763） |
| `longitude` | number | 經度（-180 ~ 180） |
| `latitude` | number | 緯度（-90 ~ 90） |
| `depth_km` | number | 震源深度（公里，≥ 0） |
| `magnitude` | number/null | 地震規模，初始為 null |
| `num_picks` | integer | 挑到的 Picks 總數 |
| `num_p_picks` | integer | P 波挑到的數量 |
| `num_s_picks` | integer | S 波挑到的數量 |
| `associated_picks` | object | 被挑到的波相的詳細資訊 (pfile) |

#### associated_picks 結構

每個測站（例如：SHUL、B138）可包含 P 波和/或 S 波資料：

**P 波欄位：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| `phase_time` | string | 波相到時 |
| `phase_score` | number | 波相分數 (probability) |
| `polarity` | string | 初動極性：`+`(up)、`-`(down)、`x`(not-determined) |

**S 波欄位：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| `phase_time` | string | 波相到時 |
| `phase_score` | number | 波相分數 (probability) |

**注意：** 測站可以只有 P 波、只有 S 波，或兩者都有。

#### 範例

```json
{
    "add_event": {
        "event_id": 123,
        "event_time": "2024-04-09T12:06:22.763",
        "longitude": 121.51,
        "latitude": 23.756,
        "depth_km": 3.932,
        "magnitude": null,
        "num_picks": 15,
        "num_p_picks": 10,
        "num_s_picks": 5,
        "associated_picks": {
            "SHUL": {
                "P": {
                    "phase_time": "2024-04-09T12:06:24.280000",
                    "phase_score": 0.914,
                    "polarity": "+"
                },
                "S": {
                    "phase_time": "2024-04-09T12:06:25.800000",
                    "phase_score": 0.816
                }
            },
            "B138": {
                "P": {
                    "phase_time": "2024-04-09T12:06:40.730000",
                    "phase_score": 0.782,
                    "polarity": "-"
                }
            },
            "EGC":{
                "P": {
                    "phase_time": "2024-04-09T12:06:41.730000",
                    "phase_score": 0.782,
                    "polarity": "x"
                }
            },            
            "WPL": {
                "S": {
                    "phase_time": "2024-04-09T12:06:42.770000",
                    "phase_score": 0.365
                }
            }
        }
    }
}
```

---

### 2. update_location - 更新位置資訊

當地震定位結果更新時發送此訊息。

#### 欄位說明

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| `event_id` | integer | 地震事件的 index |
| `longitude` | number | 經度（-180 ~ 180） |
| `latitude` | number | 緯度（-90 ~ 90） |
| `depth_km` | number | 震源深度（公里，≥ 0） |
| `magnitude` | number | 地震規模 |
| `associated_picks` | object | 關聯的測站波相資料（含距離與方位角資訊） |

#### associated_picks 結構（update_location）

**P 波和 S 波共同欄位：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| `distance_km` | number | 震央距離（公里，≥ 0） |
| `azimuth` | number | 方位角（0 ~ 360） |
| `takeoff_angle` | number | 出射角（0 ~ 180） |
| `magnitude` | number | 測站規模 |

#### 範例

```json
{
    "update_location": {
        "event_id": 123,
        "longitude": 121.512,
        "latitude": 23.758,
        "depth_km": 4.1,
        "magnitude": 2.5,
        "associated_picks": {
            "SHUL": {
                "P": {
                    "distance_km": 4.0,
                    "azimuth": 43,
                    "takeoff_angle": 139,
                    "magnitude": 0.710143
                },
                "S": {
                    "distance_km": 4.5,
                    "azimuth": 45,
                    "takeoff_angle": 140,
                    "magnitude": 0.816
                }
            },
            "B138": {
                "P": {
                    "distance_km": 4.0,
                    "azimuth": 43,
                    "takeoff_angle": 139,
                    "magnitude": 0.710143
                }
            }
        }
    }
}
```

---

### 3. update_focal - 更新震源機制解

當震源機制解計算完成時發送此訊息。

#### 欄位說明

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| `event_id` | integer | 地震事件的 index |
| `strike` | number | 走向（度，0 ~ 360） |
| `strike_err` | number | 走向誤差（度，≥ 0） |
| `dip` | number | 傾角（度，0 ~ 90） |
| `dip_err` | number | 傾角誤差（度，≥ 0） |
| `rake` | number | 滑移角（度，-180 ~ 180） |
| `rake_err` | number | 滑移角誤差（度，≥ 0） |
| `quality_index` | integer | Quality Index provided by [Wu et al., 2008](https://pubs.geoscienceworld.org/ssa/bssa/article/98/2/651/350113/Focal-Mechanism-Determination-in-Taiwan-by-Genetic) |
| `num_of_polarity` | integer | 使用的極性數量 |

#### 範例

```json
{
    "update_focal": {
        "event_id": 123,
        "strike": 120,
        "strike_err": 5,
        "dip": 30,
        "dip_err": 3,
        "rake": -90,
        "rake_err": 7,
        "quality_index": 2,
        "num_of_polarity": 10
    }
}
```