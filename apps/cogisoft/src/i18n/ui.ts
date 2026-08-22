// UI string dictionaries. Keep keys flat and stable; add a key to BOTH locales.
// Used via the helpers in ./utils.ts — never hardcode UI copy in components.
// Stage labels (`STAGE 00 · DISCOVERY`) are a brand ritual and stay English in
// both locales — they live in $lib/config, not here.
//
// Voice: first person singular. There is no team yet, and "we" collapses on the
// first call. Contractors get named as contractors once they exist.

export const languages = {
  en: "English",
  ru: "Русский",
} as const;

export type Lang = keyof typeof languages;

export const defaultLang: Lang = "en";

export const ui = {
  en: {
    "nav.phases": "How it works",
    "nav.offers": "Offers",
    "lang.aria": "Switch language",

    // ── Root: the hub ──────────────────────────────────────────────────────
    "root.hero.eyebrow": "Project & contract work",
    "root.hero.title": "I build the thing. Then I stay and run it",
    "root.hero.sub":
      "A funnel, an app, an internal tool, a process worth optimising — whatever the job needs. Then I run it: I watch it, report the numbers, repair the drift. For as long as it's needed.",
    "root.hero.cta": "Start a conversation",
    "root.hero.secondary": "How it works",

    "loop.title": "What gets built varies and it ends — a funnel, an app, an internal tool, an optimisation. How it is run is always the same and it does not end: watch, report, repair.",
    "build.1": "Funnel",
    "build.2": "App",
    "build.3": "Internal tool",
    "build.4": "Optimisation",
    "run.1": "Watch",
    "run.2": "Report",
    "run.3": "Repair",
    "loop.phase1": "Phase 1",
    "loop.phase2": "Phase 2",
    "loop.build.caption": "built once",
    "loop.run.caption": "run as long as needed",

    "phases.label": "How it works",
    "phases.title": "Two phases, not one project.",
    "phases.intro":
      "A project that ends and drives away is worth little. Anything built starts drifting on day one: integrations break, channels change, formats age, data grows. The value shows up where someone keeps it alive.",
    "phase1.label": "Phase 1",
    "phase1.title": "Build",
    "phase1.body":
      "Fixed scope, fixed term, fixed price. You end up with a working solution and the documentation to run it.",
    "phase1.1": "Funnel and acquisition",
    "phase1.2": "App or service",
    "phase1.3": "Internal tools and automation",
    "phase1.4": "Data, integrations, reporting",
    "phase1.5": "Infrastructure and deploys",
    "phase2.label": "Phase 2",
    "phase2.title": "Run",
    "phase2.body":
      "Monthly, against an SLA. I answer for it being alive, the numbers being visible, and the drift being repaired.",
    "phase2.1": "Monitoring and uptime",
    "phase2.2": "Analytics and a numbers report",
    "phase2.3": "Drift: fixing what came apart",
    "phase2.4": "Changes as they're needed",
    "phase2.5": "A review call every month",

    "offers.label": "Offers",
    "offers.title": "A fixed scope against one specific pain.",
    "offers.intro":
      "Not a service menu. Each offer names a situation, promises something measurable, and says out loud what it does not include.",
    "offers.proto": "Prototype",
    "offers.more": "Read the offer",

    "cases.label": "Cases",
    "cases.title": "What has shipped.",

    "notfor.label": "Not for you if",
    "notfor.title": "Better said before the call.",
    "notfor.1":
      "You need hands for hourly development. I sell a solution and its life afterwards, not hours.",
    "notfor.2":
      "You want it built and then we part ways. That's fine, but then I don't answer for where it is in six months — and it's a different conversation about price.",
    "notfor.3":
      "You need the result next week. Building takes weeks; the first honest numbers take a few more.",
    "notfor.4":
      "Nobody on your side owns their half — decisions, replies, access. I can keep a system alive, but I can't be the one deciding what it should do.",

    "who.label": "Who does this",
    "who.body":
      "Vladimir Beliaev. An engineer who builds it and then operates it — product, data, infrastructure. The work I do as a hired specialist lives on vvbeliaev.dev.",

    // ── Offer: signals (the proto-offer) ───────────────────────────────────
    "hero.eyebrow": "Demand before code",
    "hero.title": "Signals before software",
    "hero.sub":
      "I don't sell development hours. I test demand with live experiments in real traffic — and build only what the market already confirmed.",
    "hero.cta": "Talk through a hypothesis",
    "hero.secondary": "How it works",

    "manifesto.label": "Why market-first",
    "manifesto.commodity.label": "The commodity",
    "manifesto.commodity.title": "Anyone can ship",
    "manifesto.commodity.body":
      "AI made building cheap. A working product takes days now — so code is no longer an edge, and everyone's demo looks the same.",
    "manifesto.edge.label": "The edge",
    "manifesto.edge.title": "Few know what to ship",
    "manifesto.edge.body":
      "The scarce asset is market knowledge: what to build, for whom, and how it will reach them. That's what I manufacture — as evidence, not opinions.",
    "manifesto.conclusion":
      "So I invert the order: demand first, product last — with an honest “stop” when the signal isn't there.",
    "numbers.1.value": "42%",
    "numbers.1.label": "of startups die from “no market need” — CB Insights",
    "numbers.2.value": "days",
    "numbers.2.label": "to ship a product with AI",
    "numbers.3.value": "5",
    "numbers.3.label": "gates before product code",

    "funnel.label": "The funnel",
    "funnel.title": "Five hypotheses. MVP comes last — on purpose.",
    "funnel.intro":
      "Most agencies start at stage 04. I get there only after the market has said yes four times. Enter at any stage — every one ends with evidence, or an honest stop that saves you months.",
    "funnel.kill":
      "No signal → I stop, say so, and hand over what the market actually said. Saved months are a result too.",
    "funnel.kill.prefix": "Kill criteria",

    "stage.discovery.q": "Is there a signal at all?",
    "stage.discovery.method": "Niche recon: pains, search demand, competitor density.",
    "stage.discovery.artifact": "Signal map + ranked hypotheses",
    "stage.discovery.gate": "One hypothesis worth betting on.",

    "stage.offer.q": "Will anyone pay?",
    "stage.offer.method": "A landing page with a real offer, pushed into paid traffic.",
    "stage.offer.artifact": "Payment intent + CAC estimate",
    "stage.offer.gate": "The market votes with intent.",

    "stage.attention.q": "Can attention be earned?",
    "stage.attention.method": "Short-form content experiments on TikTok, YouTube and Instagram.",
    "stage.attention.artifact": "Repeatable format + cost of attention",
    "stage.attention.gate": "A channel that repeats without luck.",

    "stage.community.q": "Does the audience stay?",
    "stage.community.method": "An audience accumulator in Telegram or Discord.",
    "stage.community.artifact": "Living core + retention",
    "stage.community.gate": "People return on their own.",

    "stage.mvp.q": "Will the base pay — and stay?",
    "stage.mvp.method": "An MVP launched to the audience already accumulated: payment first, then retention.",
    "stage.mvp.artifact": "Working monetization",
    "stage.mvp.gate": "Revenue that retains.",

    "contact.label": "Contact",
    "contact.title": "Bring me a belief",
    "contact.sub": "I'll test it against the market and come back with evidence — either way.",
    "contact.note": "One message is enough: what you believe, and where you think the demand is.",

    "footer.tag": "Project & contract work",

    "notfound.title": "Page not found",
    "notfound.body": "This page doesn't exist or has moved.",
    "notfound.back": "Back to the signal",
  },
  ru: {
    "nav.phases": "Как это устроено",
    "nav.offers": "Офферы",
    "lang.aria": "Сменить язык",

    // ── Корень: хаб ────────────────────────────────────────────────────────
    "root.hero.eyebrow": "Проектная и подрядная работа",
    "root.hero.title": "Собираю решение. И остаюсь его вести",
    "root.hero.sub":
      "Воронка, приложение, внутренний инструмент, процесс, который стоит оптимизировать, — что нужно, то и собираю. Дальше веду: слежу, что живо, показываю цифры, чиню дрейф. Столько, сколько нужно.",
    "root.hero.cta": "Написать",
    "root.hero.secondary": "Как это устроено",

    "loop.title": "Собираемое разное и оно кончается — воронка, приложение, внутренний инструмент, оптимизация. Ведомое всегда одинаковое и не кончается: слежу, показываю, чиню.",
    "build.1": "Воронка",
    "build.2": "Приложение",
    "build.3": "Внутренний инструмент",
    "build.4": "Оптимизация",
    "run.1": "Слежу",
    "run.2": "Показываю",
    "run.3": "Чиню",
    "loop.phase1": "Фаза 1",
    "loop.phase2": "Фаза 2",
    "loop.build.caption": "собираю один раз",
    "loop.run.caption": "веду, пока нужно",

    "phases.label": "Как это устроено",
    "phases.title": "Две фазы, а не один проект.",
    "phases.intro":
      "Проект, который закончился и уехал, стоит немного. Любое собранное начинает дрейфовать с первого дня: ломаются интеграции, меняются каналы, устаревают форматы, растут данные. Ценность там, где это кто-то держит живым.",
    "phase1.label": "Фаза 1",
    "phase1.title": "Собираю",
    "phase1.body":
      "Фиксированный объём, срок и цена. На выходе — работающее решение и документация, по которой его можно вести.",
    "phase1.1": "Воронка и привлечение",
    "phase1.2": "Приложение или сервис",
    "phase1.3": "Внутренние тулы и автоматизация",
    "phase1.4": "Данные, интеграции, отчётность",
    "phase1.5": "Инфраструктура и выкатка",
    "phase2.label": "Фаза 2",
    "phase2.title": "Веду",
    "phase2.body":
      "Ежемесячно, под SLA. Отвечаю за то, что решение живо, цифры видны, а дрейф починен.",
    "phase2.1": "Мониторинг и аптайм",
    "phase2.2": "Аналитика и отчёт по цифрам",
    "phase2.3": "Дрейф: чиню то, что разъехалось",
    "phase2.4": "Доработки по мере надобности",
    "phase2.5": "Разбор раз в месяц",

    "offers.label": "Офферы",
    "offers.title": "Зафиксированный объём под конкретную боль.",
    "offers.intro":
      "Не меню услуг. Каждый оффер называет ситуацию, обещает измеримое и вслух говорит, что в него не входит.",
    "offers.proto": "Прототип",
    "offers.more": "Читать оффер",

    "cases.label": "Кейсы",
    "cases.title": "Что уже сделано.",

    "notfor.label": "Кому не подходит",
    "notfor.title": "Лучше сказать до созвона.",
    "notfor.1":
      "Нужны руки на почасовую разработку. Я продаю решение и его жизнь дальше, а не часы.",
    "notfor.2":
      "Нужно собрать и разойтись. Так можно, но тогда я не отвечаю за то, где это окажется через полгода, — и это другой разговор о цене.",
    "notfor.3":
      "Результат нужен на следующей неделе. Сборка — это недели, первые честные цифры — ещё несколько.",
    "notfor.4":
      "Внутри некому отвечать за свою половину: решения, ответы, доступы. Держать систему живой я могу, решать за вас, что она должна делать, — нет.",

    "who.label": "Кто это делает",
    "who.body":
      "Владимир Беляев. Инженер, который сам собирает и сам эксплуатирует: продукт, данные, инфраструктура. Работы, которые я делаю как наёмный специалист, — на vvbeliaev.dev.",

    // ── Оффер: сигналы (прото-оффер) ───────────────────────────────────────
    "hero.eyebrow": "Спрос до кода",
    "hero.title": "Сначала сигналы. Потом софт",
    "hero.sub":
      "Не продаю часы разработки. Проверяю спрос живыми экспериментами в реальном трафике — и строю только то, что рынок уже подтвердил.",
    "hero.cta": "Обсудить гипотезу",
    "hero.secondary": "Как это устроено",

    "manifesto.label": "Почему market-first",
    "manifesto.commodity.label": "Коммодити",
    "manifesto.commodity.title": "Собрать может каждый",
    "manifesto.commodity.body":
      "AI сделал разработку дешёвой: рабочий продукт — за дни. Код перестал быть преимуществом, и все демо выглядят одинаково.",
    "manifesto.edge.label": "Преимущество",
    "manifesto.edge.title": "Мало кто знает, что собирать",
    "manifesto.edge.body":
      "Дефицит — рыночное знание: что строить, для кого и как это дойдёт до людей. Его я и произвожу — в виде доказательств, а не мнений.",
    "manifesto.conclusion":
      "Поэтому переворачиваю порядок: сначала спрос, продукт — последним, с честным «стоп», если сигнала нет.",
    "numbers.1.value": "42%",
    "numbers.1.label": "стартапов умирают от «no market need» — CB Insights",
    "numbers.2.value": "дни",
    "numbers.2.label": "столько занимает собрать продукт с AI",
    "numbers.3.value": "5",
    "numbers.3.label": "gate до продуктового кода",

    "funnel.label": "Воронка",
    "funnel.title": "Пять гипотез. MVP — последним, и это осознанно.",
    "funnel.intro":
      "Большинство агентств начинают со ступени 04. Я дохожу до неё только после того, как рынок четыре раза сказал «да». Заходить можно на любую ступень — каждая заканчивается доказательством или честным «стоп», который экономит месяцы.",
    "funnel.kill":
      "Нет сигнала → останавливаюсь, говорю прямо и отдаю то, что на самом деле сказал рынок. Сэкономленные месяцы — тоже результат.",
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
    "contact.title": "Принесите гипотезу",
    "contact.sub": "Проверю её на рынке и вернусь с доказательствами — в любую сторону.",
    "contact.note": "Одного сообщения достаточно: во что верите и где, по-вашему, спрос.",

    "footer.tag": "Проектная и подрядная работа",

    "notfound.title": "Страница не найдена",
    "notfound.body": "Такой страницы нет или она переехала.",
    "notfound.back": "Назад к сигналу",
  },
} as const;

export type UIKey = keyof (typeof ui)[typeof defaultLang];
