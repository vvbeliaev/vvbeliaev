# social — визуальный кит Corona Bloom

Обложки и шеринговые карточки под платформы в теме **Corona Bloom** (см.
`../../../DESIGN.md`). Все собраны по одному рецепту «скайбокс под HUD»: градиент
космос→хтоника, коралловый уголёк, холодная nebula, мерцающее звёздное поле
(seeded, маска-затухание вниз), линии созвездий по боковым полям, затем читаемый
вордмарк + mono-таглайн + курсор-уголёк. Семейно связаны с баннером профиля
(`../corona-bloom-banner.svg`).

## Файлы

| Файл | Размер | Куда | Заметки |
| :-- | :-- | :-- | :-- |
| `youtube-banner.{svg,png}` | 2560×1440 | YouTube — шапка канала | Весь текст в центральной **safe-zone 1546×423** (на мобиле/десктопе края режутся; TV видит весь холст). Грузить `.png`. |
| `vertical-9x16.{svg,png}` | 1080×1920 | IG Stories · TikTok · Reels-обложка | V-mark-герой + вордмарк. |
| `square-1x1.{svg,png}` | 1080×1080 | Посты (IG / общие) | Сбалансированный квадрат. |
| `og-1200x630.{svg,png}` | 1200×630 | Превью ссылок (Telegram / X / og:image сайта) | Лэндскейп-карточка. |

- **`.svg`** — мастер-исходник (с анимацией мерцания для веба).
- **`.png`** — статичный экспорт для загрузки. Площадки берут растр, не SVG;
  анимация в загрузку не идёт (YouTube/IG/TikTok рендерят статикой). YouTube-PNG
  ≈1.7 MB, в лимите 6 MB.

## Перегенерация

`generate.py` — единый источник правды (палитра, раскладки, seeded-звёзды).
Меняешь параметры там → пересобираешь SVG:

```bash
python3 workspace/assets/social/generate.py
```

Затем экспорт SVG→PNG в точный размер (headless Chrome; `$W`/`$H` = размеры файла):

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
printf '<img src="%s" style="display:block;width:%spx;height:%spx">' youtube-banner.svg 2560 1440 > _p.html
"$CHROME" --headless --disable-gpu --force-device-scale-factor=1 \
  --window-size=2560,1440 --screenshot=youtube-banner.png "file://$PWD/_p.html"
rm _p.html
```

## Правки

- Цвета/шрифты — только из `DESIGN.md` (токены Corona Bloom). Новые не вводить.
- Хендл-футер — `@vvbeliaev` (сквозной для всех каналов), не домен.
- Тронул раскладку → пересобрал SVG → переэкспортировал PNG → глянул глазами.
