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
    "manifesto.body":
      "Most products don't die from bad code — they die from no demand. Building is expensive; testing a signal is cheap. So we invert the default order: evidence first, product last. Every stage ends with data you can act on — including an honest “stop” when the signal isn't there.",
    "numbers.1.value": "42%",
    "numbers.1.label": "of startups die from “no market need” — CB Insights",
    "numbers.2.value": "0",
    "numbers.2.label": "lines of code before the offer converts",
    "numbers.3.value": "5",
    "numbers.3.label": "hypotheses in one funnel — signal to revenue",
    "numbers.4.value": "2–4",
    "numbers.4.label": "weeks per validation cycle",

    "funnel.label": "The funnel",
    "funnel.title": "Five hypotheses. MVP comes last — on purpose.",
    "funnel.intro":
      "Most agencies start at stage 04. We get there only after the market has said yes four times. Enter at any stage — every one ends with evidence, or an honest stop that saves you months.",
    "funnel.method": "Method",
    "funnel.artifact": "You get",
    "funnel.gate": "Gate to next stage",
    "funnel.kill":
      "No signal → we stop, say so, and hand over what the market actually said. Saved months are a result too.",
    "funnel.kill.prefix": "Kill criteria",

    "stage.discovery.q": "Is there a signal at all?",
    "stage.discovery.method": "Niche recon: pains, search demand, competitor density.",
    "stage.discovery.artifact": "A signal map with ranked hypotheses.",
    "stage.discovery.gate": "One hypothesis worth betting on.",

    "stage.offer.q": "Will anyone pay?",
    "stage.offer.method": "A landing page with a real offer, pushed into paid traffic.",
    "stage.offer.artifact": "Conversion to payment intent and a first CAC estimate.",
    "stage.offer.gate": "The market votes with intent.",

    "stage.attention.q": "Can we earn attention?",
    "stage.attention.method": "Short-form content experiments on TikTok, YouTube and Instagram.",
    "stage.attention.artifact": "A repeatable format and a known cost of attention.",
    "stage.attention.gate": "A channel that repeats without luck.",

    "stage.community.q": "Does the audience stay?",
    "stage.community.method": "An audience accumulator in Telegram or Discord.",
    "stage.community.artifact": "A living core and measured attention retention.",
    "stage.community.gate": "People return on their own.",

    "stage.mvp.q": "Will the base pay — and stay?",
    "stage.mvp.method": "An MVP launched to the audience we accumulated: payment first, then retention.",
    "stage.mvp.artifact": "Working monetization on your own audience.",
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
    "manifesto.body":
      "Продукты редко умирают от плохого кода — они умирают от отсутствия спроса. Строить дорого, проверять сигнал — дёшево. Поэтому мы переворачиваем порядок по умолчанию: сначала доказательства, продукт — последним. Каждая ступень заканчивается данными, с которыми можно действовать, — включая честное «стоп», если сигнала нет.",
    "numbers.1.value": "42%",
    "numbers.1.label": "стартапов умирают от «no market need» — CB Insights",
    "numbers.2.value": "0",
    "numbers.2.label": "строк кода до того, как оффер конвертит",
    "numbers.3.value": "5",
    "numbers.3.label": "гипотез в одной воронке — от сигнала до выручки",
    "numbers.4.value": "2–4",
    "numbers.4.label": "недели на цикл проверки",

    "funnel.label": "Воронка",
    "funnel.title": "Пять гипотез. MVP — последним, и это осознанно.",
    "funnel.intro":
      "Большинство агентств начинают со ступени 04. Мы доходим до неё только после того, как рынок четыре раза сказал «да». Заходить можно на любую ступень — каждая заканчивается доказательством или честным «стоп», который экономит месяцы.",
    "funnel.method": "Метод",
    "funnel.artifact": "Вы получаете",
    "funnel.gate": "Переход дальше",
    "funnel.kill":
      "Нет сигнала → останавливаемся, говорим прямо и отдаём то, что на самом деле сказал рынок. Сэкономленные месяцы — тоже результат.",
    "funnel.kill.prefix": "Kill criteria",

    "stage.discovery.q": "Есть ли сигнал вообще?",
    "stage.discovery.method": "Разведка ниши: боли, поисковый спрос, плотность конкурентов.",
    "stage.discovery.artifact": "Карта сигналов с ранжированными гипотезами.",
    "stage.discovery.gate": "Одна гипотеза, на которую стоит ставить.",

    "stage.offer.q": "Готовы ли платить?",
    "stage.offer.method": "Лендинг с настоящим оффером в платном трафике.",
    "stage.offer.artifact": "Конверсия в намерение платить и первая оценка CAC.",
    "stage.offer.gate": "Рынок голосует намерением.",

    "stage.attention.q": "Умеем ли привлекать внимание?",
    "stage.attention.method": "Контент-эксперименты в TikTok, YouTube и Instagram.",
    "stage.attention.artifact": "Воспроизводимый формат и известная стоимость внимания.",
    "stage.attention.gate": "Канал, который повторяется не на удаче.",

    "stage.community.q": "Остаётся ли аудитория?",
    "stage.community.method": "Аккумулятор аудитории в Telegram или Discord.",
    "stage.community.artifact": "Живое ядро и измеренное удержание внимания.",
    "stage.community.gate": "Люди возвращаются сами.",

    "stage.mvp.q": "Платит ли база — и остаётся ли?",
    "stage.mvp.method": "MVP на накопленную аудиторию: сначала оплата, потом удержание.",
    "stage.mvp.artifact": "Работающая монетизация на собственной аудитории.",
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
