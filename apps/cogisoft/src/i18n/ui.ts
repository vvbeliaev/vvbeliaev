// UI string dictionaries. Keep keys flat and stable; add a key to BOTH locales.
// Used via the helpers in ./utils.ts — never hardcode UI copy in components.
// Stage labels (`STAGE 00 · DISCOVERY`) are a brand ritual and stay English in
// both locales — they live in $lib/config, not here.

export const languages = {
  en: "English",
  ru: "Русский",
} as const;

export type Lang = keyof typeof languages;

export const defaultLang: Lang = "en";

export const ui = {
  en: {
    "nav.how": "How we work",
    "lang.aria": "Switch language",

    "hero.eyebrow": "Market-first studio",
    "hero.title": "Signals before software",
    "hero.sub":
      "We don't sell development hours. We validate demand with live experiments in real traffic — and build only what the market already confirmed.",
    "hero.cta": "Run a signal check",
    "hero.secondary": "How we work",

    "manifesto.label": "Why market-first",
    "manifesto.commodity.label": "The commodity",
    "manifesto.commodity.title": "Anyone can ship",
    "manifesto.commodity.body":
      "AI made building cheap. A working product takes days now — so code is no longer an edge, and everyone's demo looks the same.",
    "manifesto.edge.label": "The edge",
    "manifesto.edge.title": "Few know what to ship",
    "manifesto.edge.body":
      "The scarce asset is market knowledge: what to build, for whom, and how it will reach them. That's what we manufacture — as evidence, not opinions.",
    "manifesto.conclusion":
      "So we invert the order: demand first, product last — with an honest “stop” when the signal isn't there.",
    "numbers.1.value": "42%",
    "numbers.1.label": "of startups die from “no market need” — CB Insights",
    "numbers.2.value": "days",
    "numbers.2.label": "to ship a product with AI",
    "numbers.3.value": "5",
    "numbers.3.label": "gates before product code",

    "funnel.label": "The funnel",
    "funnel.title": "Five hypotheses. MVP comes last — on purpose.",
    "funnel.intro":
      "Most agencies start at stage 04. We get there only after the market has said yes four times. Enter at any stage — every one ends with evidence, or an honest stop that saves you months.",
    "funnel.kill":
      "No signal → we stop, say so, and hand over what the market actually said. Saved months are a result too.",
    "funnel.kill.prefix": "Kill criteria",

    "stage.discovery.q": "Is there a signal at all?",
    "stage.discovery.method": "Niche recon: pains, search demand, competitor density.",
    "stage.discovery.artifact": "Signal map + ranked hypotheses",
    "stage.discovery.gate": "One hypothesis worth betting on.",

    "stage.offer.q": "Will anyone pay?",
    "stage.offer.method": "A landing page with a real offer, pushed into paid traffic.",
    "stage.offer.artifact": "Payment intent + CAC estimate",
    "stage.offer.gate": "The market votes with intent.",

    "stage.attention.q": "Can we earn attention?",
    "stage.attention.method": "Short-form content experiments on TikTok, YouTube and Instagram.",
    "stage.attention.artifact": "Repeatable format + cost of attention",
    "stage.attention.gate": "A channel that repeats without luck.",

    "stage.community.q": "Does the audience stay?",
    "stage.community.method": "An audience accumulator in Telegram or Discord.",
    "stage.community.artifact": "Living core + retention",
    "stage.community.gate": "People return on their own.",

    "stage.mvp.q": "Will the base pay — and stay?",
    "stage.mvp.method": "An MVP launched to the audience we accumulated: payment first, then retention.",
    "stage.mvp.artifact": "Working monetization",
    "stage.mvp.gate": "Revenue that retains.",

    "contact.label": "Contact",
    "contact.title": "Bring us a belief",
    "contact.sub": "We'll test it against the market and come back with evidence — either way.",
    "contact.note": "One email is enough: what you believe, and where you think the demand is.",

    "footer.tag": "Market-first studio",

    "notfound.title": "Page not found",
    "notfound.body": "This page doesn't exist or has moved.",
    "notfound.back": "Back to the signal",
  },
  ru: {
    "nav.how": "Как мы работаем",
    "lang.aria": "Сменить язык",

    "hero.eyebrow": "Market-first студия",
    "hero.title": "Сначала сигналы. Потом софт",
    "hero.sub":
      "Мы не продаём часы разработки. Мы проверяем спрос живыми экспериментами в реальном трафике — и строим только то, что рынок уже подтвердил.",
    "hero.cta": "Проверить сигнал",
    "hero.secondary": "Как мы работаем",

    "manifesto.label": "Почему market-first",
    "manifesto.commodity.label": "Коммодити",
    "manifesto.commodity.title": "Собрать может каждый",
    "manifesto.commodity.body":
      "AI сделал разработку дешёвой: рабочий продукт — за дни. Код перестал быть преимуществом, и все демо выглядят одинаково.",
    "manifesto.edge.label": "Преимущество",
    "manifesto.edge.title": "Мало кто знает, что собирать",
    "manifesto.edge.body":
      "Дефицит — рыночное знание: что строить, для кого и как это дойдёт до людей. Его мы и производим — в виде доказательств, а не мнений.",
    "manifesto.conclusion":
      "Поэтому мы переворачиваем порядок: сначала спрос, продукт — последним, с честным «стоп», если сигнала нет.",
    "numbers.1.value": "42%",
    "numbers.1.label": "стартапов умирают от «no market need» — CB Insights",
    "numbers.2.value": "дни",
    "numbers.2.label": "столько занимает собрать продукт с AI",
    "numbers.3.value": "5",
    "numbers.3.label": "gate до продуктового кода",

    "funnel.label": "Воронка",
    "funnel.title": "Пять гипотез. MVP — последним, и это осознанно.",
    "funnel.intro":
      "Большинство агентств начинают со ступени 04. Мы доходим до неё только после того, как рынок четыре раза сказал «да». Заходить можно на любую ступень — каждая заканчивается доказательством или честным «стоп», который экономит месяцы.",
    "funnel.kill":
      "Нет сигнала → останавливаемся, говорим прямо и отдаём то, что на самом деле сказал рынок. Сэкономленные месяцы — тоже результат.",
    "funnel.kill.prefix": "Kill criteria",

    "stage.discovery.q": "Есть ли сигнал вообще?",
    "stage.discovery.method": "Разведка ниши: боли, поисковый спрос, плотность конкурентов.",
    "stage.discovery.artifact": "Карта сигналов + гипотезы",
    "stage.discovery.gate": "Одна гипотеза, на которую стоит ставить.",

    "stage.offer.q": "Готовы ли платить?",
    "stage.offer.method": "Лендинг с настоящим оффером в платном трафике.",
    "stage.offer.artifact": "Намерение платить + оценка CAC",
    "stage.offer.gate": "Рынок голосует намерением.",

    "stage.attention.q": "Умеем ли привлекать внимание?",
    "stage.attention.method": "Контент-эксперименты в TikTok, YouTube и Instagram.",
    "stage.attention.artifact": "Формат + стоимость внимания",
    "stage.attention.gate": "Канал, который повторяется не на удаче.",

    "stage.community.q": "Остаётся ли аудитория?",
    "stage.community.method": "Аккумулятор аудитории в Telegram или Discord.",
    "stage.community.artifact": "Живое ядро + удержание",
    "stage.community.gate": "Люди возвращаются сами.",

    "stage.mvp.q": "Платит ли база — и остаётся ли?",
    "stage.mvp.method": "MVP на накопленную аудиторию: сначала оплата, потом удержание.",
    "stage.mvp.artifact": "Работающая монетизация",
    "stage.mvp.gate": "Выручка, которая удерживается.",

    "contact.label": "Связь",
    "contact.title": "Принесите нам гипотезу",
    "contact.sub": "Мы проверим её на рынке и вернёмся с доказательствами — в любую сторону.",
    "contact.note": "Одного письма достаточно: во что верите и где, по-вашему, спрос.",

    "footer.tag": "Market-first студия",

    "notfound.title": "Страница не найдена",
    "notfound.body": "Такой страницы нет или она переехала.",
    "notfound.back": "Назад к сигналу",
  },
} as const;

export type UIKey = keyof (typeof ui)[typeof defaultLang];
