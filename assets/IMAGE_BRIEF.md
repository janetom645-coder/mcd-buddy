# 🎨 麦门助手 · 图像生成需求书（IMAGE_BRIEF.md）

本文件用于**外部工具生成插画**，生成后回传给我集成进项目。
所有图片请严格遵循下方「通用风格规范」，以保证整套视觉是**同一个家族**。

---

## 一、通用风格规范（每张都要带上）

### 英文风格串（Midjourney / DALL·E / SD / Flux 等）

```text
cute flat vector cartoon illustration, kawaii chibi style, thick soft rounded
outlines, limited flat colors, McDonald's brand palette: red #DA291C and golden
yellow #FFC72C, warm brown #7B4A21, leaf green #6FBF4A, cream background #FFF8E7,
simple dot eyes with white highlight, rosy cheeks, friendly smile, minimal
shading, no gradients, no photorealism, no 3D render, sticker-like clean shapes,
centered composition with generous margin, high clarity
```

### 中文风格串（即梦 / 文心一格 / 通义万相 / 可图 等）

```text
可爱扁平矢量卡通风，Q 版 chibi 风格，粗而圆润的描边，纯色平涂，
配色限定为麦当劳红 #DA291C、金拱黄 #FFC72C、暖棕 #7B4A21、生菜绿 #6FBF4A，
奶油底色 #FFF8E7，豆豆眼带白色高光，腮红，友好微笑，
极简阴影，无渐变，无写实，无 3D 渲染，贴纸感，构图居中留白
```

### 负面提示词（Negative）

```text
text, letters, words, watermark, signature, logo, trademark, realistic photo,
3D render, gradient, neon, dark background, cluttered, extra limbs, deformed face,
multiple characters overlapping, low quality, blurry
```

> ⚠️ **重要：所有图片都不要出现文字**。AI 生成文字容易出错，项目里的文字我会用 SVG 精确叠加。

---

## 二、角色设定（所有图共用）

**麦麦** —— 一只圆滚滚的汉堡小人：

| 特征 | 描述 |
|---|---|
| 身体 | 汉堡造型：上层芝麻面包 + 生菜 + 芝士 + 牛肉饼 + 下层面包 |
| 头顶 | 一顶小小的**金色拱形小帽**（两条金色弧线，注意：是抽象拱形，**不是**麦当劳官方 Logo） |
| 五官 | 两只黑色豆豆眼（带白色高光）、微笑的嘴、两坨粉色腮红 |
| 四肢 | 短手短脚，圆润可爱 |
| 气质 | 憨厚、热情、有点小馋 |

---

## 三、逐张需求清单

### 🔴 P0 · 必做（6 张）

#### A1 · 吉祥物主形象 `mascot-hero.png`

- **用途**：README 吉祥物介绍、SKILL 图标
- **尺寸 / 比例**：1024×1024，**1:1**
- **背景**：**透明**（PNG 带 alpha）
- **提示词**：
  > A cute chibi burger character mascot standing upright and waving one hand,
  > friendly big smile, tiny golden arch hat on top of the sesame bun head,
  > lettuce cheese and patty layers forming the body, short stubby arms and legs,
  > {英文风格串}, isolated on transparent background, PNG with alpha channel, 1:1
- **中文**：可爱的 Q 版汉堡小人吉祥物，正面站立单手挥手，露出友好大笑，头顶戴一顶金色拱形小帽，生菜芝士牛肉饼层构成身体，短手短脚，{中文风格串}，透明背景，1:1

#### B1 · 修行录场景 `scene-practice.png`

- **用途**：README 模块配图
- **尺寸 / 比例**：1600×900，**16:9**
- **背景**：奶油色 #FFF8E7（可有，也可透明）
- **提示词**：
  > The cute burger mascot sitting cross-legged in a peaceful meditation pose,
  > eyes gently closed with a serene smile, several glowing achievement badges,
  > medals and small stars floating around it, soft cream background,
  > {英文风格串}, 16:9
- **中文**：可爱的汉堡小人盘腿打坐修行，双眼轻闭面带安详微笑，周围漂浮着发光的成就徽章、奖牌和小星星，奶油色背景，{中文风格串}，16:9

#### B2 · 团餐指挥官场景 `scene-group-meal.png`

- **用途**：README 模块配图
- **尺寸 / 比例**：1600×900，**16:9**
- **提示词**：
  > The cute burger mascot wearing a headset like a team commander, holding a
  > small clipboard, standing confidently in front of a row of three smaller
  > burger characters and a big serving tray, {英文风格串}, 16:9
- **中文**：可爱的汉堡小人戴着耳麦像团餐指挥官，手拿小记事板，自信地站在一排三个小汉堡伙伴和一只大餐盘前面，{中文风格串}，16:9

#### B3 · 隐藏菜单实验室场景 `scene-hidden-menu.png`

- **用途**：README 模块配图
- **尺寸 / 比例**：1600×900，**16:9**
- **提示词**：
  > The cute burger mascot wearing a white lab coat and safety goggles, holding
  > a test tube, standing next to a big glass flask that contains a tiny burger,
  > sparkles and bubbles around, {英文风格串}, 16:9
- **中文**：可爱的汉堡小人穿着白大褂、戴着护目镜，手拿试管，旁边是一只装着迷你汉堡的大玻璃烧瓶，周围有闪光和气泡，{中文风格串}，16:9

#### B4 · 每日运势签场景 `scene-fortune.png`

- **用途**：README 模块配图
- **尺寸 / 比例**：1600×900，**16:9**
- **提示词**：
  > The cute burger mascot pulling a fortune stick out of a red fortune-stick
  > cup, a paper fortune slip floating in the air with sparkles and stars around,
  > {英文风格串}, 16:9
- **中文**：可爱的汉堡小人正从红色签筒里抽出一支签，一张签纸在空中飘起，周围有闪光和小星星，{中文风格串}，16:9

#### C1 · README 头图插画（无文字）`banner-art.png`

- **用途**：README 顶部大图（文字我后期用 SVG 叠加）
- **尺寸 / 比例**：3400×1000，**约 3.4:1**
- **背景**：**透明**（PNG 带 alpha）
- **提示词**：
  > Wide horizontal banner illustration, the cute burger mascot in the center
  > waving cheerfully, surrounded by a big burger, a carton of french fries, a
  > soft drink cup with straw and a sundae, abstract golden arch shapes as
  > background decoration, absolutely no text or letters,
  > {英文风格串}, transparent background, 3400x1000
- **中文**：宽幅横版头图插画，可爱的汉堡小人在中间开心挥手，周围环绕着大汉堡、一盒薯条、一杯插吸管的饮料和一杯冰淇淋，背景用抽象的金色拱形做装饰，**绝对不要出现任何文字**，{中文风格串}，透明背景，3400×1000

---

### 🟡 P1 · 推荐（6 张表情包）

**生成方法**：先用 A1 生成满意的主形象，再用**图生图 / 角色参考 / 垫图**功能生成以下 6 张，保证是同一个角色。

- **尺寸 / 比例**：1024×1024，**1:1**
- **背景**：**透明**

| 文件名 | 表情 | 英文提示词补充 |
|---|---|---|
| `mascot-happy.png` | 开心大笑、眼睛弯成月牙、举起双手 | `laughing joyfully with crescent-shaped closed eyes, both arms raised up` |
| `mascot-hungry.png` | 流口水、眼巴巴看着食物 | `drooling with sparkling eyes, staring hungrily at a burger` |
| `mascot-shocked.png` | 惊讶、嘴巴张成 O 形、眼睛睁大 | `shocked expression, mouth open in an O shape, wide surprised eyes` |
| `mascot-full.png` | 吃撑了、摸着圆肚子、满足 | `very full and satisfied, patting a round belly, happy contented face` |
| `mascot-sad.png` | 委屈、眼角含泪、耷拉着 | `sad and pouting, teary eyes, drooping shoulders` |
| `mascot-thinking.png` | 思考、手托下巴、头顶问号 | `thinking pose with one hand on chin, a question mark floating above` |

> 统一前缀：`same cute burger mascot character as reference, {表情描述}, {英文风格串}, isolated on transparent background`

---

### 🟢 P2 · 选做（2 张，用于社交传播涨 Star）

#### D1 · 分享卡片背景 `share-card-bg.png`

- **尺寸 / 比例**：1080×1440，**3:4 竖版**
- **提示词**：
  > Vertical share card background, cream base with a thick red rounded border
  > frame, the cute burger mascot peeking in from the bottom right corner,
  > golden arch decoration at the top, large empty clean area in the middle for
  > text overlay, no text, {英文风格串}, 1080x1440

#### D2 · 社交传播图 `social-promo.png`

- **尺寸 / 比例**：1080×1080，**1:1**
- **提示词**：
  > Square social media promo illustration, the cute burger mascot holding a
  > large blank signboard with both hands, confetti and stars bursting around,
  > cheerful festive mood, no text on the signboard,
  > {英文风格串}, 1080x1080

---

## 四、合规红线（必读）

参赛规则对内容合规要求严格，生成时务必避开：

- ❌ **不要生成麦当劳官方 Logo**（金拱门 M 商标）、真实产品包装、真实门店照片
  → 需要品牌感时，用**抽象的金色拱形弧线**表达即可
- ❌ 画面中**不要出现任何文字**
- ❌ 不要出现真人、真人照片
- ❌ 不要出现任何暗示「暴饮暴食」「浪费」「拜金」「低俗」的意象
- ❌ 不要出现其他品牌的产品或 Logo
- ✅ 保持健康、阳光、可爱的正向基调

---

## 五、回传要求

生成后请按以下方式给我：

| 项 | 要求 |
|---|---|
| 文件名 | 严格使用上表中的文件名（如 `mascot-hero.png`） |
| 格式 | PNG 优先（透明背景的必须 PNG） |
| 分辨率 | 按各张要求；不足也没关系，但**不要低于**要求的 60% |
| 数量 | P0 六张优先，P1/P2 有精力再做 |
| 打包 | 直接放进一个文件夹发我即可 |

拿到后我会：
1. 检查尺寸与透明通道
2. 放进 `assets/` 并更新 README / 分享卡片的引用
3. 用 SVG 把文字精确叠加到头图与分享卡上
4. 跑一遍回归，确认所有引用路径正常

> 💡 如果某张反复生成不满意，告诉我，我可以调整提示词，或者用我现有的 SVG 方案兜底——**SVG 版本已经在项目里跑通了，不依赖外部图片**。
