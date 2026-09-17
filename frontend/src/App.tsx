import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, DashboardStats, DiscoveryQuery, IntegrationStatus, Lead, NotificationBotProbe, NotificationBotStatus, PipelineStatus, SearchProfile, SearchProfileInput, Settings, Source, TelegramDialog, TelegramStatus } from "./api";

type Page = "dashboard" | "leads" | "sources" | "discovery" | "profiles" | "settings";

const pageLabels: Record<Page, string> = {
  dashboard: "Обзор",
  leads: "Лиды",
  sources: "Источники",
  discovery: "Поиск источников",
  profiles: "Профили поиска",
  settings: "Настройки",
};

function Score({ value }: { value: number }) {
  const tone = value >= 90 ? "hot" : value >= 75 ? "good" : "possible";
  return <span className={`score ${tone}`}>{value}</span>;
}

function PageGuide({ page }: { page: Page }) {
  const guides: Record<Page, ReactNode> = {
    dashboard: <><p><b>Здесь ничего настраивать не нужно.</b> Это сводка работы радара.</p><ol><li>«Сообщения сегодня» — сколько сообщений сохранено из активных источников.</li><li>«Прошли pre-filter» — сколько сообщений совпало с активными профилями поиска.</li><li>«Проверено AI» и «Лиды» — сколько совпадений обработано и показано пользователю.</li><li>HOT, GOOD и POSSIBLE показывают силу сигнала. Чем выше число, тем полезнее потенциальный запрос.</li><li>Если данные не изменились, обновите страницу: экран пока не обновляется автоматически.</li></ol><p><b>Первый запуск:</b> подключите Telegram в «Настройках», добавьте чат в «Источниках», создайте профиль поиска и нажмите у источника «Анализ 100».</p></>,
    leads: <><p>Здесь находятся сообщения, которые прошли активный профиль поиска и AI-проверку.</p><ol><li>Используйте фильтры сверху, чтобы выбрать оценку, категорию, источник, дату или feedback.</li><li>Нажмите «Подробнее», чтобы увидеть исходный текст, автора и причину срабатывания.</li><li>«Открыть в Telegram» ведёт к оригинальному сообщению, если для него доступна ссылка.</li><li>«Хороший лид» подтверждает полезное совпадение, «Не лид» отмечает ошибочное. Эти оценки улучшают рейтинг источника.</li><li>«Подготовить ответ» создаёт только черновик — приложение ничего не отправляет собеседнику автоматически.</li></ol><p><b>Не видите новое сообщение?</b> Убедитесь, что источник ACTIVE, профиль включён, затем обновите страницу.</p></>,
    sources: <><p>Источник — канал или группа, сообщения которой нужно проверять.</p><ol><li>Нажмите «Показать чаты», чтобы увидеть группы и каналы подключённого Telegram-аккаунта.</li><li>Найдите нужный чат и нажмите «Добавить в источники». Личные переписки не показываются.</li><li>Если есть ссылка <code>t.me/...</code>, её можно вставить в поле ручного добавления.</li><li>Статус ACTIVE означает постоянный мониторинг новых сообщений; «Пауза» временно его выключает.</li><li>«Анализ 100» загружает последние 100 сообщений. Используйте его после добавления источника или изменения профилей.</li><li>«Удалить» удаляет источник вместе с его сохранёнными сообщениями и лидами.</li></ol></>,
    discovery: <><p>Этот раздел ищет <b>новые публичные каналы и группы</b>, а не сообщения внутри уже подключённых чатов.</p><ol><li>Введите короткую тему, например <code>хартстоун</code>, <code>киберспорт</code> или <code>разработка сайтов</code>.</li><li>Нажмите «Добавить» — запрос сохранится. Можно добавить несколько запросов.</li><li>Оставьте нужные запросы включёнными и нажмите «Запустить поиск».</li><li>Результаты появятся справа. Нажмите «Вступить» только у подходящих чатов.</li><li>После вступления чат исчезнет из результатов и появится в «Источниках».</li><li>«Очистить результаты» удаляет только неподключённые находки и не затрагивает активные источники.</li></ol><p>Для хороших результатов используйте 1–3 тематических слова. Длинный вопрос обычно работает хуже.</p></>,
    profiles: <><p><b>Профиль определяет, какие сообщения считать совпадениями.</b> Для простого мониторинга достаточно названия и позитивных ключевых слов.</p><ol><li><b>Название</b> — понятное имя правила, например «Hearthstone» или «Заказы на сайты».</li><li><b>Описание</b> — необязательная заметка для пользователя.</li><li><b>Категории</b> — дополнительная AI-проверка. Для обычного поиска слов оставьте поле пустым.</li><li><b>Позитивные ключи</b> — слова через запятую. Совпадение любого слова запускает обработку. Регистр не важен.</li><li><b>Стоп-слова</b> — если найдено любое из них, сообщение отбрасывается.</li><li><b>Порог уведомления</b> влияет только на отправку ботом. Для каждого совпадения поставьте 0.</li><li><b>Включать вакансии</b> разрешает сообщения о найме; иначе вакансии исключаются.</li><li><b>Отправлять уведомления</b> работает после подключения Notification Bot.</li></ol><div className="guide-example"><b>Пример Hearthstone</b><code>Позитивные: консид, варлок, рога, маг, прист, друид, хант, шаман</code><code>Стоп-слова: продажа, реклама</code><code>Категории: оставить пустыми · Порог: 0</code></div><p>Активные профили работают по принципу «ИЛИ»: сообщению достаточно совпасть хотя бы с одним. После изменения профиля откройте «Источники» и нажмите «Анализ 100», чтобы проверить историю. Новые сообщения проверяются автоматически.</p></>,
    settings: <><p>Здесь подключаются Telegram-аккаунт, бот уведомлений и задаются общие правила.</p><ol><li>Для мониторинга раскройте инструкцию «Где получить api_id и api_hash» и выполните мастер подключения аккаунта.</li><li>Для уведомлений создайте отдельного бота через <b>@BotFather</b>, откройте его и нажмите «Запустить».</li><li>Вставьте токен в блок «Бот уведомлений», найдите чат и сохраните подключение.</li><li>«Порог уведомлений» используется как общий порог для лидов без отдельного профиля.</li><li>В профиле поиска также должны быть включены уведомления.</li></ol><p>Токены и Telegram credentials хранятся на сервере в зашифрованном виде и не возвращаются в браузер.</p></>,
  };
  return <details className={`page-guide ${page === "profiles" ? "important" : ""}`} open={page === "profiles"}><summary><span>?</span><div><b>Как пользоваться разделом</b><small>Пошаговая инструкция и примеры</small></div><i>⌄</i></summary><div className="page-guide-body">{guides[page]}</div></details>;
}

export function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    api.authStatus()
      .then((result) => setAuthenticated(result.authenticated))
      .catch(() => setAuthenticated(false));
  }, []);

  if (authenticated === null) return <div className="login-shell"><div className="radar-loader" /></div>;
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;
  return <RadarApp onLogout={() => setAuthenticated(false)} />;
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try { await api.login(password); setPassword(""); onSuccess(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось войти"); }
    finally { setBusy(false); }
  };
  return <div className="login-shell"><section className="login-card"><div className="brand"><span className="radar-dot" /> Lead Radar</div><p className="eyebrow">Защищённая панель</p><h1>Вход администратора</h1><p>Введите пароль, настроенный на backend.</p><form onSubmit={submit}><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="Пароль" required autoFocus />{error && <div className="notice error">{error}</div>}<button disabled={busy}>{busy ? "Проверка…" : "Войти"}</button></form></section></div>;
}

function RadarApp({ onLogout }: { onLogout: () => void }) {
  const [page, setPage] = useState<Page>("dashboard");
  const [sources, setSources] = useState<Source[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [telegram, setTelegram] = useState<TelegramStatus | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [dashboard, setDashboard] = useState<DashboardStats | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [queries, setQueries] = useState<DiscoveryQuery[]>([]);
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextSources, nextLeads, nextSettings, nextTelegram, nextIntegrations, nextDashboard, nextPipeline, nextQueries, nextProfiles] = await Promise.all([
        api.sources(),
        api.leads(),
        api.settings(),
        api.telegramStatus(),
        api.integrationStatus(),
        api.dashboard(),
        api.pipelineStatus(),
        api.discoveryQueries(),
        api.searchProfiles(),
      ]);
      setSources(nextSources);
      setLeads(nextLeads);
      setSettings(nextSettings);
      setTelegram(nextTelegram);
      setIntegrations(nextIntegrations);
      setDashboard(nextDashboard);
      setPipeline(nextPipeline);
      setQueries(nextQueries);
      setProfiles(nextProfiles);
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onLogout();
        return;
      }
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  const connectedSources = sources.filter((source) => source.status !== "DISCOVERED");

  const content = {
    dashboard: <Dashboard leads={leads} sources={connectedSources} stats={dashboard} pipeline={pipeline} />,
    leads: <Leads leads={leads} sources={connectedSources} onFeedback={async (id, value) => { await api.feedback(id, value); await load(); }} />,
    sources: <Sources sources={connectedSources} reload={load} />,
    discovery: <Discovery queries={queries} sources={sources} reload={load} />,
    profiles: <Profiles profiles={profiles} reload={load} />,
    settings: <SettingsPage settings={settings} telegram={telegram} integrations={integrations} onChange={setSettings} reload={load} />,
  }[page];

  return (
    <div className="shell">
      <aside>
        <div className="brand"><span className="radar-dot" /> Lead Radar</div>
        <nav>
          {(Object.keys(pageLabels) as Page[]).map((item) => (
            <button className={page === item ? "active" : ""} onClick={() => setPage(item)} key={item}>
              {pageLabels[item]}
            </button>
          ))}
        </nav>
        <button className="logout" onClick={async () => { await api.logout(); onLogout(); }}>Выйти</button>
        <div className={`connection ${telegram?.connected ? "online" : ""}`}><span /> Telegram {telegram?.connected ? "подключён" : "не подключён"}</div>
      </aside>
      <main>
        <header><div><p className="eyebrow">Telegram Lead Radar</p><h1>{pageLabels[page]}</h1></div><div className="avatar">LR</div></header>
        <PageGuide page={page} />
        {error && <div className="notice error">Backend недоступен: {error}</div>}
        {loading ? <div className="empty">Синхронизация радара…</div> : content}
      </main>
    </div>
  );
}

function Dashboard({ leads, sources, stats, pipeline }: { leads: Lead[]; sources: Source[]; stats: DashboardStats | null; pipeline: PipelineStatus | null }) {
  const active = useMemo(() => sources.filter((source) => source.status === "ACTIVE").length, [sources]);
  const topSources = useMemo(() => [...sources].filter((source) => source.source_score !== null).sort((a, b) => (b.source_score ?? 0) - (a.source_score ?? 0)).slice(0, 5), [sources]);
  return <>
    <section className="hero"><div><p className="eyebrow">Сигналы в реальном времени</p><h2>Возможности не должны теряться в шуме.</h2><p>Подключите источники — радар отфильтрует сообщения и вынесет сильные запросы наверх.</p></div><div className="sweep"><i /></div></section>
    <section className="stats">
      <article><span>Сообщения сегодня</span><strong>{stats?.messages_today ?? 0}</strong></article>
      <article><span>Прошли pre-filter</span><strong>{stats?.prefiltered_today ?? 0}</strong></article>
      <article><span>Проверено AI</span><strong>{stats?.ai_checked_today ?? 0}</strong></article>
      <article><span>Лиды сегодня</span><strong>{stats?.leads_today ?? 0}</strong></article>
    </section>
    <section className="signal-strip"><span>HOT <b>{stats?.hot_today ?? 0}</b></span><span>GOOD <b>{stats?.good_today ?? 0}</b></span><span>POSSIBLE <b>{stats?.possible_today ?? 0}</b></span><span>Подтверждено <b>{stats?.confirmed_today ?? 0}</b></span><span>Активные источники <b>{active}</b></span><span>AI retry <b>{pipeline?.retrying ?? 0}</b></span><span className={(pipeline?.failed ?? 0) > 0 ? "alert" : ""}>AI failed <b>{pipeline?.failed ?? 0}</b></span><span className={(pipeline?.notifications_failed ?? 0) > 0 ? "alert" : ""}>Bot failed <b>{pipeline?.notifications_failed ?? 0}</b></span></section>
    <section className="panel"><div className="panel-title"><h2>Последние сигналы</h2><span>{leads.length} найдено</span></div><LeadRows leads={leads.slice(0, 5)} /></section>
    <section className="panel top-sources"><div className="panel-title"><h2>Эффективность источников</h2><span>Source Score · 30 дней</span></div>{topSources.length ? topSources.map((source) => <div className="metric-row" key={source.id}><span>{source.title}</span><i><b style={{ width: `${(source.source_score ?? 0) * 10}%` }} /></i><strong>{source.source_score?.toFixed(1)}</strong></div>) : <div className="empty">Оценка появится после анализа источников.</div>}</section>
  </>;
}

function LeadRows({ leads, onFeedback, onSelect }: { leads: Lead[]; onFeedback?: (id: number, value: "POSITIVE" | "NEGATIVE") => void; onSelect?: (lead: Lead) => void }) {
  if (!leads.length) return <div className="empty">Лидов пока нет. После подключения Telegram здесь появятся сигналы.</div>;
  return <div className="lead-list">{leads.map((lead) => <article className="lead-row" key={lead.id}>
    <Score value={lead.lead_score} />
    <div className="lead-copy"><h3>{lead.summary}</h3><p>{lead.source_title} · {lead.category.replaceAll("_", " ")}</p></div>
    {lead.message_url && <a href={lead.message_url} target="_blank" rel="noreferrer">Открыть ↗</a>}
    {onSelect && <button className="detail-button" onClick={() => onSelect(lead)}>Подробнее</button>}
    {onFeedback && <div className="feedback"><button onClick={() => onFeedback(lead.id, "POSITIVE")}>✓</button><button onClick={() => onFeedback(lead.id, "NEGATIVE")}>×</button></div>}
  </article>)}</div>;
}

function Leads({ leads, sources, onFeedback }: { leads: Lead[]; sources: Source[]; onFeedback: (id: number, value: "POSITIVE" | "NEGATIVE") => void }) {
  const [band, setBand] = useState("");
  const [category, setCategory] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [feedback, setFeedback] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [minScore, setMinScore] = useState("0");
  const [selected, setSelected] = useState<Lead | null>(null);
  const categories = useMemo(() => [...new Set(leads.map((lead) => lead.category))].sort(), [leads]);
  const visible = useMemo(() => leads.filter((lead) => {
    if (band === "HOT" && lead.lead_score < 90) return false;
    if (band === "GOOD" && (lead.lead_score < 75 || lead.lead_score >= 90)) return false;
    if (band === "POSSIBLE" && (lead.lead_score < 60 || lead.lead_score >= 75)) return false;
    if (category && lead.category !== category) return false;
    if (sourceId && lead.source_id !== Number(sourceId)) return false;
    if (feedback === "NONE" && lead.feedback !== null) return false;
    if (feedback && feedback !== "NONE" && lead.feedback !== feedback) return false;
    if (dateFrom && lead.created_at.slice(0, 10) < dateFrom) return false;
    return lead.lead_score >= Number(minScore || 0);
  }), [leads, band, category, sourceId, feedback, dateFrom, minScore]);
  return <>
    <section className="panel"><div className="panel-title"><div><p className="eyebrow">Входящие возможности</p><h2>История лидов</h2></div><span>{visible.length} записей</span></div>
      <div className="filters"><select value={band} onChange={(event) => setBand(event.target.value)}><option value="">Все уровни</option><option value="HOT">HOT 90+</option><option value="GOOD">GOOD 75–89</option><option value="POSSIBLE">POSSIBLE 60–74</option></select><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">Все категории</option>{categories.map((item) => <option key={item}>{item}</option>)}</select><select value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">Все источники</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.title}</option>)}</select><select value={feedback} onChange={(event) => setFeedback(event.target.value)}><option value="">Любой feedback</option><option value="POSITIVE">Хороший лид</option><option value="NEGATIVE">Не лид</option><option value="NONE">Без feedback</option></select><label>С даты<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label>Score от<input type="number" min="0" max="100" value={minScore} onChange={(event) => setMinScore(event.target.value)} /></label></div>
      <LeadRows leads={visible} onFeedback={onFeedback} onSelect={setSelected} />
    </section>
    {selected && <LeadDetail lead={selected} close={() => setSelected(null)} onFeedback={onFeedback} />}
  </>;
}

function LeadDetail({ lead, close, onFeedback }: { lead: Lead; close: () => void; onFeedback: (id: number, value: "POSITIVE" | "NEGATIVE") => void }) {
  const [draft, setDraft] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generate = async () => { setBusy(true); setDraftError(null); try { setDraft((await api.draftResponse(lead.id)).draft); } catch (caught) { setDraftError(caught instanceof Error ? caught.message : "Не удалось создать черновик"); } finally { setBusy(false); } };
  return <div className="modal-backdrop" onMouseDown={close}><section className="lead-detail" onMouseDown={(event) => event.stopPropagation()}><button className="modal-close" onClick={close}>×</button><div className="detail-heading"><Score value={lead.lead_score} /><div><p className="eyebrow">Карточка лида</p><h2>{lead.summary}</h2></div></div><div className="detail-grid"><div><span>Источник</span><b>{lead.source_title}</b></div><div><span>Автор</span><b>{lead.sender_username ? `@${lead.sender_username}` : "Не указан"}</b></div><div><span>Категория</span><b>{lead.category}</b></div><div><span>Услуга</span><b>{lead.service || "Не определена"}</b></div><div><span>Intent</span><b>{lead.intent}</b></div><div><span>Confidence</span><b>{Math.round(lead.confidence * 100)}%</b></div><div><span>Срочность</span><b>{lead.urgency || "Не указана"}</b></div><div><span>Бюджет</span><b>{lead.budget ? `${lead.budget} ${lead.budget_currency || ""}` : "Не указан"}</b></div><div><span>Срок</span><b>{lead.deadline || "Не указан"}</b></div><div><span>Feedback</span><b>{lead.feedback || "Нет"}</b></div></div><div className="original"><span>Оригинальное сообщение</span><p>{lead.message_text}</p></div>{lead.reason && <div className="reason"><span>Объяснение AI</span><p>{lead.reason}</p></div>}{draft && <div className="draft"><span>Черновик ответа · не отправлен</span><p>{draft}</p><button className="ghost" onClick={() => navigator.clipboard.writeText(draft)}>Копировать</button></div>}{draftError && <div className="notice error">{draftError}</div>}<div className="detail-actions">{lead.message_url && <a href={lead.message_url} target="_blank" rel="noreferrer">Открыть в Telegram ↗</a>}<button onClick={generate} disabled={busy}>{busy ? "Готовим…" : "Подготовить ответ"}</button><button onClick={() => onFeedback(lead.id, "POSITIVE")}>✓ Хороший лид</button><button onClick={() => onFeedback(lead.id, "NEGATIVE")}>× Не лид</button></div></section></div>;
}

function Sources({ sources, reload }: { sources: Source[]; reload: () => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Record<number, string>>({});
  const [dialogs, setDialogs] = useState<TelegramDialog[] | null>(null);
  const [dialogSearch, setDialogSearch] = useState("");
  const [dialogsBusy, setDialogsBusy] = useState(false);
  const [importingDialog, setImportingDialog] = useState<number | null>(null);
  const visibleDialogs = useMemo(() => {
    const needle = dialogSearch.trim().toLocaleLowerCase("ru-RU");
    if (!needle) return dialogs ?? [];
    return (dialogs ?? []).filter((dialog) => `${dialog.title} ${dialog.username ?? ""}`.toLocaleLowerCase("ru-RU").includes(needle));
  }, [dialogs, dialogSearch]);
  const loadDialogs = async () => { setDialogsBusy(true); setActionError(null); try { setDialogs(await api.telegramDialogs()); } catch (caught) { setActionError(caught instanceof Error ? caught.message : "Не удалось получить чаты Telegram"); } finally { setDialogsBusy(false); } };
  const submit = async (event: FormEvent) => { event.preventDefault(); setActionError(null); try { await api.addSource(url); setUrl(""); await reload(); } catch (caught) { setActionError(caught instanceof Error ? caught.message : "Не удалось добавить источник"); } };
  return <><form className="add-source" onSubmit={submit}><div><p className="eyebrow">Ручное добавление</p><h2>Подключить Telegram-источник</h2></div><div className="input-row"><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://t.me/example или invite-ссылка" required /><button type="submit">Добавить</button></div></form>
    {actionError && <div className="notice error">{actionError}</div>}
    <section className="panel telegram-dialogs"><div className="panel-title"><div><p className="eyebrow">Подключённый аккаунт</p><h2>Мои Telegram-чаты</h2></div><button className="ghost" onClick={loadDialogs} disabled={dialogsBusy}>{dialogsBusy ? "Загрузка…" : dialogs === null ? "Показать чаты" : "Обновить список"}</button></div>{dialogs === null ? <div className="empty compact-empty">Покажем каналы и группы, в которых аккаунт уже состоит. Личные диалоги не загружаются.</div> : <><input className="dialog-search" value={dialogSearch} onChange={(event) => setDialogSearch(event.target.value)} placeholder="Поиск по названию или @username" /><div className="dialog-list">{visibleDialogs.map((dialog) => <article key={dialog.telegram_chat_id}><div><h3>{dialog.title}</h3><p>{dialog.source_type.replaceAll("_", " ")} · {dialog.username ? `@${dialog.username}` : "приватный чат"}{dialog.participants_count ? ` · ${dialog.participants_count} участников` : ""}</p></div>{dialog.already_added ? <span className="status active">ДОБАВЛЕН</span> : <button className="ghost" disabled={importingDialog === dialog.telegram_chat_id} onClick={async () => { setImportingDialog(dialog.telegram_chat_id); setActionError(null); try { await api.importTelegramDialog(dialog.telegram_chat_id); await Promise.all([reload(), loadDialogs()]); } catch (caught) { setActionError(caught instanceof Error ? caught.message : "Не удалось добавить чат"); } finally { setImportingDialog(null); } }}>{importingDialog === dialog.telegram_chat_id ? "Добавление…" : "Добавить в источники"}</button>}</article>)}</div>{!visibleDialogs.length && <div className="empty compact-empty">Подходящих групп и каналов не найдено.</div>}</>}</section>
    <section className="panel"><div className="panel-title"><h2>Источники</h2><span>{sources.length} всего</span></div>{!sources.length ? <div className="empty">Добавьте первый публичный чат или приватную invite-ссылку.</div> : <div className="source-list">{sources.map((source) => <article key={source.id}><div><h3>{source.title}</h3><p>{source.is_public ? "Публичный" : "Приватный"} · {source.username ? `@${source.username}` : "invite link"} · score {source.source_score?.toFixed(1) ?? "—"}</p>{analysis[source.id] && <p className="analysis-result">{analysis[source.id]}</p>}</div><span className={`status ${source.status.toLowerCase()}`}>{source.status}</span><div className="source-actions">{["ACTIVE", "PAUSED"].includes(source.status) && <button className="ghost" onClick={async () => { setActionError(null); setAnalysis((old) => ({ ...old, [source.id]: "Анализ…" })); try { const result = await api.analyzeSource(source.id, 100); setAnalysis((old) => ({ ...old, [source.id]: `${result.inserted} новых · ${result.candidates} кандидатов · score ${result.source_score}` })); await reload(); } catch (caught) { setAnalysis((old) => ({ ...old, [source.id]: caught instanceof Error ? caught.message : "Ошибка анализа" })); } }}>Анализ 100</button>}<button className="ghost" onClick={async () => { setActionError(null); try { if (["DISCOVERED", "REVIEW", "UNAVAILABLE"].includes(source.status)) await api.joinSource(source.id); else await api.setSourceStatus(source.id, source.status === "ACTIVE" ? "pause" : "activate"); await reload(); } catch (caught) { setActionError(caught instanceof Error ? caught.message : "Не удалось изменить источник"); } }}>{source.status === "ACTIVE" ? "Пауза" : source.status === "PAUSED" ? "Активировать" : "Вступить"}</button><button className="ghost danger" onClick={async () => { if (!window.confirm(`Удалить источник «${source.title}» и связанные данные?`)) return; try { await api.deleteSource(source.id); await reload(); } catch (caught) { setActionError(caught instanceof Error ? caught.message : "Не удалось удалить источник"); } }}>Удалить</button></div></article>)}</div>}</section>
  </>;
}

function Discovery({ queries, sources, reload }: { queries: DiscoveryQuery[]; sources: Source[]; reload: () => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const discovered = sources.filter((source) => source.status === "DISCOVERED");
  const submit = async (event: FormEvent) => { event.preventDefault(); setMessage(null); try { await api.addDiscoveryQuery(query); setQuery(""); await reload(); } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Не удалось добавить запрос"); } };
  const run = async () => { setBusy(true); setMessage(null); try { const result = await api.runDiscovery(); setMessage(`Запросов: ${result.queries_run}, найдено: ${result.found}, добавлено: ${result.added}`); await reload(); } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Не удалось выполнить поиск"); } finally { setBusy(false); } };
  return <div className="two-column"><section className="panel"><div className="panel-title"><div><p className="eyebrow">Telegram public search</p><h2>Discovery Queries</h2></div><button className="ghost" onClick={run} disabled={busy}>{busy ? "Ищем…" : "Запустить поиск"}</button></div><form className="compact-form" onSubmit={submit}><input value={query} onChange={(event) => setQuery(event.target.value)} minLength={2} placeholder="Например: нужен разработчик сайта" required /><button>Добавить</button></form>{message && <div className="notice warning">{message}</div>}<div className="query-list">{queries.map((item) => <div key={item.id}><label className="toggle"><input type="checkbox" checked={item.enabled} onChange={async (event) => { await api.updateDiscoveryQuery(item.id, { enabled: event.target.checked }); await reload(); }} /><span />{item.query}</label><small>{item.last_run_at ? `Последний запуск: ${new Date(item.last_run_at).toLocaleString("ru-RU")}` : "Ещё не запускался"}</small><button className="ghost danger" onClick={async () => { await api.deleteDiscoveryQuery(item.id); await reload(); }}>Удалить</button></div>)}</div></section><section className="panel"><div className="panel-title"><h2>Найденные источники</h2><div className="panel-actions"><span>{discovered.length}</span><button className="ghost danger" disabled={!discovered.length} onClick={async () => { if (!window.confirm("Очистить все найденные, но ещё не подключённые источники?")) return; await api.clearDiscoveryResults(); setMessage("Результаты поиска очищены"); await reload(); }}>Очистить результаты</button></div></div>{discovered.length ? <div className="source-list">{discovered.map((source) => <article key={source.id}><div><h3>{source.title}</h3><p>@{source.username} · {source.participants_count ?? "—"} участников</p></div><span className="status">DISCOVERED</span><button className="ghost" onClick={async () => { await api.joinSource(source.id); await reload(); }}>Вступить</button></article>)}</div> : <div className="empty">Запустите поиск по активным запросам. Вступление всегда подтверждается вручную.</div>}</section></div>;
}

const emptyProfile: SearchProfileInput = { name: "", description: null, enabled: true, categories: [], positive_keywords: [], negative_keywords: [], min_score: 70, include_vacancies: false, notification_enabled: true };
const splitList = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);

function Profiles({ profiles, reload }: { profiles: SearchProfile[]; reload: () => Promise<void> }) {
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState<SearchProfileInput>(emptyProfile);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(null); try { if (editing) await api.updateSearchProfile(editing, form); else await api.addSearchProfile(form); setEditing(null); setForm(emptyProfile); await reload(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось сохранить профиль"); } };
  const edit = (profile: SearchProfile) => { setEditing(profile.id); setForm({ name: profile.name, description: profile.description, enabled: profile.enabled, categories: profile.categories, positive_keywords: profile.positive_keywords, negative_keywords: profile.negative_keywords, min_score: profile.min_score, include_vacancies: profile.include_vacancies, notification_enabled: profile.notification_enabled }); };
  const useHearthstoneTemplate = () => setForm({ ...emptyProfile, name: "Hearthstone", description: "Упоминания игровых классов и сленга", positive_keywords: ["консид", "варлок", "рога", "маг", "прист", "друид", "хант", "шаман", "паладин", "дк", "дх"], negative_keywords: ["реклама", "продажа"], min_score: 0, include_vacancies: true });
  const useItTemplate = () => setForm({ ...emptyProfile, name: "IT-заказы", description: "Поиск запросов на разработку и автоматизацию", categories: ["WEB_DEVELOPMENT", "TELEGRAM_BOTS", "CRM", "INTEGRATIONS", "AUTOMATION", "AI_LLM"], positive_keywords: ["сайт", "лендинг", "бот", "crm", "интеграция", "автоматизация"], negative_keywords: ["курс", "обучение", "резюме"], min_score: 70 });
  return <div className="two-column profiles"><form className="panel profile-form" onSubmit={submit}><p className="eyebrow">Сегментация лидов</p><h2>{editing ? "Редактировать профиль" : "Новый профиль поиска"}</h2>{!editing && <div className="template-picker"><span>Заполнить пример:</span><button type="button" className="ghost" onClick={useHearthstoneTemplate}>Hearthstone</button><button type="button" className="ghost" onClick={useItTemplate}>IT-заказы</button></div>}<label>Название<small>Короткое понятное имя правила.</small><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} minLength={2} placeholder="Например: Hearthstone" required /></label><label>Описание<small>Необязательная заметка: что именно ищет этот профиль.</small><textarea value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value || null })} /></label><label>Категории через запятую<small>Для простого поиска слов оставьте пустым. Используйте только для дополнительной AI-фильтрации.</small><input value={form.categories.join(", ")} onChange={(event) => setForm({ ...form, categories: splitList(event.target.value) })} placeholder="WEB_DEVELOPMENT, AI_LLM" /></label><label>Позитивные ключи<small>Введите слова через запятую. Сработает любое из них, регистр букв не важен.</small><input value={form.positive_keywords.join(", ")} onChange={(event) => setForm({ ...form, positive_keywords: splitList(event.target.value) })} placeholder="консид, варлок, рога, маг" /></label><label>Стоп-слова<small>Сообщение будет исключено, если содержит хотя бы одно такое слово.</small><input value={form.negative_keywords.join(", ")} onChange={(event) => setForm({ ...form, negative_keywords: splitList(event.target.value) })} placeholder="реклама, продажа" /></label><label>Порог уведомления<small>0 — уведомлять о каждом совпадении; 70 — только о более сильных.</small><input type="number" min="0" max="100" value={form.min_score} onChange={(event) => setForm({ ...form, min_score: Number(event.target.value) })} /></label><label className="toggle"><input type="checkbox" checked={form.include_vacancies} onChange={(event) => setForm({ ...form, include_vacancies: event.target.checked })} /><span />Включать вакансии</label><label className="toggle"><input type="checkbox" checked={form.notification_enabled} onChange={(event) => setForm({ ...form, notification_enabled: event.target.checked })} /><span />Отправлять уведомления</label>{error && <div className="notice error">{error}</div>}<div className="form-actions"><button>{editing ? "Сохранить" : "Создать профиль"}</button>{editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm(emptyProfile); }}>Отмена</button>}</div></form><section className="panel"><div className="panel-title"><h2>Профили</h2><span>{profiles.length}</span></div>{profiles.length ? <div className="profile-list">{profiles.map((profile) => <article key={profile.id}><div><h3>{profile.name}</h3><p>{profile.categories.join(", ") || "Все категории"} · score от {profile.min_score}</p><small>+ {profile.positive_keywords.join(", ") || "базовые ключи"}<br />− {profile.negative_keywords.join(", ") || "базовые стоп-слова"}</small></div><label className="toggle"><input type="checkbox" checked={profile.enabled} onChange={async (event) => { await api.updateSearchProfile(profile.id, { enabled: event.target.checked }); await reload(); }} /><span />Активен</label><div className="source-actions"><button className="ghost" onClick={() => edit(profile)}>Изменить</button><button className="ghost danger" onClick={async () => { await api.deleteSearchProfile(profile.id); await reload(); }}>Удалить</button></div></article>)}</div> : <div className="empty">Без профилей используется общая фильтрация из настроек.</div>}</section></div>;
}

function SettingsPage({ settings, telegram, integrations, onChange, reload }: { settings: Settings | null; telegram: TelegramStatus | null; integrations: IntegrationStatus | null; onChange: (value: Settings) => void; reload: () => Promise<void> }) {
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [editingCredentials, setEditingCredentials] = useState(false);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authStep, setAuthStep] = useState<"PHONE" | "CODE" | "PASSWORD">("PHONE");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const [botStatus, setBotStatus] = useState<NotificationBotStatus | null>(null);
  const [botToken, setBotToken] = useState("");
  const [botProbe, setBotProbe] = useState<NotificationBotProbe | null>(null);
  const [botChatId, setBotChatId] = useState("");
  const [botError, setBotError] = useState<string | null>(null);
  const [botBusy, setBotBusy] = useState(false);
  useEffect(() => { api.notificationBotStatus().then(setBotStatus).catch(() => setBotStatus(null)); }, []);
  if (!settings) return <div className="empty">Настройки недоступны</div>;
  const update = async (patch: Partial<Settings>) => onChange(await api.updateSettings(patch));
  const submitCredentials = async (event: FormEvent) => {
    event.preventDefault(); setAuthBusy(true); setAuthError(null);
    try { await api.telegramConfigure(Number(apiId), apiHash.trim()); setApiHash(""); setEditingCredentials(false); await reload(); }
    catch (caught) { setAuthError(caught instanceof Error ? caught.message : "Не удалось сохранить Telegram API"); }
    finally { setAuthBusy(false); }
  };
  const submitAuth = async (event: FormEvent) => {
    event.preventDefault(); setAuthBusy(true); setAuthError(null);
    try {
      if (authStep === "PHONE") { const result = await api.telegramAuthStart(phone); setAuthToken(result.auth_token); setAuthStep("CODE"); }
      else if (authStep === "CODE" && authToken) { const result = await api.telegramAuthCode(authToken, code); if (result.status === "PASSWORD_REQUIRED") setAuthStep("PASSWORD"); else await reload(); }
      else if (authStep === "PASSWORD" && authToken) { await api.telegramAuthPassword(authToken, password); setPassword(""); await reload(); }
    } catch (caught) { setAuthError(caught instanceof Error ? caught.message : "Ошибка авторизации"); }
    finally { setAuthBusy(false); }
  };
  const probeBot = async (event: FormEvent) => {
    event.preventDefault(); setBotBusy(true); setBotError(null);
    try {
      const result = await api.probeNotificationBot(botToken.trim());
      setBotProbe(result);
      if (result.chats.length === 1) setBotChatId(result.chats[0].chat_id);
    } catch (caught) { setBotError(caught instanceof Error ? caught.message : "Не удалось проверить бота"); }
    finally { setBotBusy(false); }
  };
  const connectBot = async () => {
    if (!botChatId.trim()) { setBotError("Выберите чат или введите его Chat ID"); return; }
    setBotBusy(true); setBotError(null);
    try {
      const result = await api.configureNotificationBot(botToken.trim(), botChatId.trim());
      setBotStatus(result); setBotToken(""); setBotProbe(null); setBotChatId(""); await reload();
    } catch (caught) { setBotError(caught instanceof Error ? caught.message : "Не удалось подключить бота"); }
    finally { setBotBusy(false); }
  };
  return <section className="settings-grid">
    <article className="panel telegram-card wide"><p className="eyebrow">MTProto account</p><h2>Подключение Telegram</h2>
      <details className="setup-guide" open={!telegram?.configured}><summary>Где получить api_id и api_hash</summary><ol><li>Откройте <a href="https://my.telegram.org" target="_blank" rel="noreferrer">my.telegram.org ↗</a> и войдите по номеру.</li><li>Перейдите в <b>API development tools</b>.</li><li>Создайте приложение: название любое, Platform — Desktop.</li><li>Скопируйте <b>App api_id</b> и <b>App api_hash</b> в форму ниже.</li></ol><p>api_hash хранится на backend в зашифрованном виде и никогда не возвращается в браузер.</p></details>
      {(!telegram?.configured || editingCredentials) ? <form className="auth-form credentials-form" onSubmit={submitCredentials}><h3>Шаг 1 · Telegram API</h3><div className="credential-grid"><input type="number" min="1" value={apiId} onChange={(event) => setApiId(event.target.value)} placeholder="api_id" required /><input type="password" minLength={32} value={apiHash} onChange={(event) => setApiHash(event.target.value)} placeholder="api_hash" autoComplete="off" required /></div>{authError && <div className="notice error">{authError}</div>}<div className="form-actions"><button type="submit" disabled={authBusy}>{authBusy ? "Сохранение…" : "Сохранить и продолжить"}</button>{telegram?.configured && <button type="button" className="ghost" onClick={() => { setEditingCredentials(false); setAuthError(null); }}>Отмена</button>}</div></form> : telegram.connected ? <div className="account"><div className="account-mark">✓</div><div><strong>{telegram.account_name || telegram.username || "Telegram user"}</strong><p>{telegram.phone}{telegram.username ? ` · @${telegram.username}` : ""}</p></div><button className="ghost danger" onClick={async () => { await api.telegramDisconnect(); setAuthStep("PHONE"); await reload(); }}>Отключить</button></div> : <form className="auth-form" onSubmit={submitAuth}>
        <div className="auth-heading"><h3>Шаг 2 · Авторизация аккаунта</h3>{authStep === "PHONE" && <button type="button" className="text-button" onClick={() => setEditingCredentials(true)}>Изменить API credentials</button>}</div>
        <p>{authStep === "PHONE" ? "Введите телефон аккаунта в международном формате." : authStep === "CODE" ? "Введите код, который прислал Telegram." : "Аккаунт защищён облачным паролем 2FA."}</p>
        {authStep === "PHONE" && <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+7 999 123-45-67" autoComplete="tel" required />}
        {authStep === "CODE" && <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Код Telegram" inputMode="numeric" autoComplete="one-time-code" required />}
        {authStep === "PASSWORD" && <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Пароль 2FA" autoComplete="current-password" required />}
        {authError && <div className="notice error">{authError}</div>}<button type="submit" disabled={authBusy}>{authBusy ? "Подключение…" : authStep === "PHONE" ? "Получить код" : "Продолжить"}</button>
      </form>}
    </article>
    <article className="panel telegram-card wide"><p className="eyebrow">Telegram Bot API</p><h2>Бот уведомлений</h2>
      <details className="setup-guide" open={!botStatus?.configured}><summary>Как создать и подключить бота</summary><ol><li>Откройте в Telegram официального <b>@BotFather</b> и отправьте <code>/newbot</code>.</li><li>Придумайте имя и username, затем скопируйте выданный токен.</li><li>Откройте созданного бота и обязательно нажмите <b>«Запустить»</b> или отправьте <code>/start</code>.</li><li>Вставьте токен ниже и нажмите <b>«Проверить и найти чаты»</b>.</li><li>Выберите найденный чат и сохраните. Бот сразу отправит туда тестовое сообщение.</li></ol><p>Для группы: добавьте туда бота и отправьте в группе <code>/start@username_бота</code>, затем повторите поиск. Токен сохраняется только на backend в зашифрованном виде.</p></details>
      {botStatus?.configured ? <div className="account"><div className="account-mark">✓</div><div><strong>{botStatus.bot_name || (botStatus.bot_username ? `@${botStatus.bot_username}` : "Notification Bot")}</strong><p>{botStatus.chat_title || "Чат уведомлений"}{botStatus.chat_id ? ` · ID ${botStatus.chat_id}` : ""}</p></div><button className="ghost danger" disabled={botBusy} onClick={async () => { setBotBusy(true); setBotError(null); try { await api.disconnectNotificationBot(); setBotStatus({ configured: false, bot_username: null, bot_name: null, chat_id: null, chat_title: null }); await reload(); } catch (caught) { setBotError(caught instanceof Error ? caught.message : "Не удалось отключить бота"); } finally { setBotBusy(false); } }}>Отключить</button></div> : <form className="auth-form" onSubmit={probeBot}><h3>Шаг 1 · Токен от BotFather</h3><p>Токен выглядит примерно так: <code>123456789:AA...</code></p><input type="password" minLength={20} value={botToken} onChange={(event) => { setBotToken(event.target.value); setBotProbe(null); }} placeholder="Вставьте токен бота" autoComplete="off" required /><button type="submit" disabled={botBusy}>{botBusy ? "Проверяю…" : "Проверить и найти чаты"}</button>
        {botProbe && <div className="bot-destination"><h3>Шаг 2 · Куда отправлять</h3><p>Бот найден: <b>{botProbe.bot_username ? `@${botProbe.bot_username}` : botProbe.bot_name}</b></p>{botProbe.chats.length ? <div className="bot-chat-list">{botProbe.chats.map((chat) => <label key={chat.chat_id} className={botChatId === chat.chat_id ? "selected" : ""}><input type="radio" name="notification-chat" value={chat.chat_id} checked={botChatId === chat.chat_id} onChange={() => setBotChatId(chat.chat_id)} /><span><b>{chat.title}</b><small>{chat.type} · ID {chat.chat_id}</small></span></label>)}</div> : <div className="notice">Чаты пока не найдены. Отправьте боту <b>/start</b>, затем снова нажмите «Проверить и найти чаты».</div>}<label className="manual-chat"><span>Или введите Chat ID вручную</span><input value={botChatId} onChange={(event) => setBotChatId(event.target.value)} placeholder="Например: 123456789" inputMode="numeric" /></label><button type="button" onClick={connectBot} disabled={botBusy || !botChatId.trim()}>{botBusy ? "Подключаю…" : "Сохранить и отправить тест"}</button></div>}
      </form>}
      {botError && <div className="notice error">{botError}</div>}
    </article>
    <article className="panel"><p className="eyebrow">Качество сигнала</p><h2>Порог уведомлений</h2><div className="range-value">{settings.minimum_notification_score}</div><input type="range" min="0" max="100" value={settings.minimum_notification_score} onChange={(event) => update({ minimum_notification_score: Number(event.target.value) })} /></article>
    <article className="panel"><p className="eyebrow">Фильтрация</p><h2>Вакансии</h2><label className="toggle"><input type="checkbox" checked={settings.include_vacancies} onChange={(event) => update({ include_vacancies: event.target.checked })} /><span />Включать штатные вакансии</label></article>
    <article className="panel"><p className="eyebrow">Pipeline</p><h2>AI & Notification Bot</h2><div className="integration"><span>Notification Bot</span><b className={integrations?.notification_bot_configured ? "ok" : ""}>{integrations?.notification_bot_configured ? "Настроен" : "Не подключён"}</b></div><div className="integration"><span>AI Provider</span><b className={integrations?.ai_configured ? "ok" : ""}>{integrations?.ai_configured ? `${integrations.ai_provider}${integrations.ai_model ? ` · ${integrations.ai_model}` : ""}` : "Не настроен"}</b></div></article>
  </section>;
}
