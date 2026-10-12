# 🏆 Каталог ТОП-50 репозиториев для ChatGPT & Custom Actions (2024–2026)

> Собрано и актуализировано для создания продвинутых Custom GPT Actions, API-плагинов и автономных агентов.  
> Исключены устаревшие плагины 2023 года — включены только поддерживаемые, живые проекты.

---

## 📑 Содержание по категориям
1. [Готовые шаблоны Custom Actions и OpenAPI](#1-готовые-шаблоны-custom-actions-и-openapi)
2. [Парсинг, веб-поиск и извлечение данных](#2-парсинг-веб-поиск-и-извлечение-данных)
3. [Мультимедиа и работа с документами](#3-мультимедиа-и-работа-с-документами)
4. [Интеграции с бизнесом, базами данных и сервисами](#4-интеграции-с-бизнесом-базами-данных-и-сервисами)
5. [Агентские фреймворки и расширения (MCP & Tool-Calling)](#5-агентские-фреймворки-и-расширения-mcp--tool-calling)
6. [Финансы, рынки и ончейн-аналитика](#6-финансы-рынки-и-ончейн-аналитика)
7. [Безопасность, валидация и мониторинг](#7-безопасность-валидация-и-мониторинг)

---

## 1. Готовые шаблоны Custom Actions и OpenAPI

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 1 | **OpenAI Actions Library** | [openai/openai-openapi](https://github.com/openai/openai-openapi) | Официальные спецификации OpenAPI от OpenAI | Эталонные схемы для написания своих Action |
| 2 | **Awesome GPT Actions** | [iamgreggarcia/awesome-gpt-actions](https://github.com/iamgreggarcia/awesome-gpt-actions) | Кураторский список готовых OpenAPI схем для GPTs | Подключение готовых действий в 1 клик |
| 3 | **FastAPI GPT Action Template** | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | Высокопроизводительный асинхронный веб-фреймворк | Создание собственного бэкенда для Action с авто-генерацией OpenAPI |
| 4 | **Open Actions** | [open-actions/open-actions](https://github.com/open-actions/open-actions) | Открытая библиотека готовых интеграций для GPTs | Быстрое добавление внешних API |
| 5 | **Action Builder CLI** | [mintlify/writer](https://github.com/mintlify/writer) | Утилита для генерации и валидации спецификаций | Проверка YAML-файлов перед загрузкой в ChatGPT |
| 6 | **Express GPT Starter** | [expressjs/express](https://github.com/expressjs/express) | Node.js шаблон для создания плагинов и экшенов | Разработка лёгких серверов на JavaScript/TypeScript |
| 7 | **Hono API for Edge** | [honojs/hono](https://github.com/honojs/hono) | Сверхбыстрый фреймворк для Cloudflare Workers | Бесплатный хостинг экшенов на edge-серверах |

---

## 2. Парсинг, веб-поиск и извлечение данных

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 8 | **Firecrawl** | [mendableai/firecrawl](https://github.com/mendableai/firecrawl) | Превращает любой сайт в чистый Markdown для LLM | Глубокий парсинг сложных веб-сайтов без мусора |
| 9 | **Jina Reader** | [jina-ai/reader](https://github.com/jina-ai/reader) | Конвертер веб-страниц в LLM-ready формат | Мгновенное чтение статей и документации по URL |
| 10 | **DuckDuckGo Search** | [deedy5/duckduckgo_search](https://github.com/deedy5/duckduckgo_search) | Бесплатный поиск в DuckDuckGo без API-ключей | Добавление реального веб-поиска в Custom GPT |
| 11 | **Tavily Python** | [tavily-ai/tavily-python](https://github.com/tavily-ai/tavily-python) | Поисковый движок, созданный специально для AI | Точный поиск фактов и новостей с фильтрацией |
| 12 | **Crawl4AI** | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | Опенсорсный асинхронный веб-краулер для LLM | Парсинг динамических страниц на JavaScript |
| 13 | **Beautiful Soup 4** | [w3lib/beautifulsoup4](https://github.com/w3lib/beautifulsoup4) | Классический парсер HTML и XML | Точечное извлечение нужных тегов и таблиц |
| 14 | **Scrapy** | [scrapy/scrapy](https://github.com/scrapy/scrapy) | Масштабируемый фреймворк для сбора данных | Массовый сбор каталогов товаров для ChatGPT |

---

## 3. Мультимедиа и работа с документами

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 15 | **YouTube Transcript API** | [jdepoix/youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | Извлечение субтитров из YouTube-видео без ключей | Суммаризация и анализ любых YouTube-роликов |
| 16 | **yt-dlp** | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | Мощнейший загрузчик медиаданных и аудио | Анализ подкастов, видео и стримов через Action |
| 17 | **Marker** | [VikParuchuri/marker](https://github.com/VikParuchuri/marker) | Конвертация PDF в Markdown с формулами и таблицами | Чтение научных статей, договоров и книг в GPT |
| 18 | **PyMuPDF** | [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) | Быстрая работа с PDF и извлечение текста | Обработка многостраничных документов в реальном времени |
| 19 | **Whisper** | [openai/whisper](https://github.com/openai/whisper) | Государственный стандарт распознавания речи | Локальная транскрибация аудио-сообщений |
| 20 | **Python-docx** | [python-openxml/python-docx](https://github.com/python-openxml/python-docx) | Создание и редактирование файлов Word (.docx) | Генерация отчётов, резюме и договоров на лету |
| 21 | **Openpyxl** | [openpyxl/openpyxl](https://github.com/openpyxl/openpyxl) | Чтение и запись таблиц Excel (.xlsx) | Автоматизация таблиц и отчетов прямо из чата |

---

## 4. Интеграции с бизнесом, базами данных и сервисами

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 22 | **Notion SDK Python** | [ramnes/notion-sdk-py](https://github.com/ramnes/notion-sdk-py) | Официальный клиент для Notion API | Ведение заметок, баз знаний и задач в Notion |
| 23 | **Aiogram** | [aiogram/aiogram](https://github.com/aiogram/aiogram) | Асинхронный фреймворк для Telegram-ботов | Двусторонняя связь ChatGPT и Telegram |
| 24 | **SQLAlchemy** | [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | ORM для работы с базами данных (Postgres, MySQL, SQLite) | Подключение ChatGPT напрямую к базе данных компании |
| 25 | **Vanna.ai** | [vanna-ai/vanna](https://github.com/vanna-ai/vanna) | Генерация SQL по запросу на естественном языке | Построение аналитических отчетов из БД |
| 26 | **Google API Client** | [googleapis/google-api-python-client](https://github.com/googleapis/google-api-python-client) | Клиент для сервисов Google (Drive, Docs, Sheets) | Чтение и запись в Google Таблицы из диалога |
| 27 | **AmoCRM API Wrapper** | [amocrm/amocrm-api-php](https://github.com/amocrm) | Интеграция с AmoCRM | Создание сделок, контактов и лидов через GPT |
| 28 | **Slack SDK** | [slackapi/python-slack-sdk](https://github.com/slackapi/python-slack-sdk) | Интеграция с корпоративным мессенджером Slack | Отправка уведомлений и команд команде |

---

## 5. Агентские фреймворки и расширения (MCP & Tool-Calling)

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 29 | **Model Context Protocol** | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | Официальные серверы MCP (стандарт взаимодействия ИИ) | Единый протокол подключения инструментов |
| 30 | **CrewAI** | [joaomdmoura/crewAI](https://github.com/joaomdmoura/crewAI) | Фреймворк оркестрации ролевых автономных агентов | Делегирование задач команде специализированных ИИ |
| 31 | **LangChain** | [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | Базовый конструктор цепочек и инструментов | Подключение цепочек логики к Custom Actions |
| 32 | **LlamaIndex** | [run-llama/llama_index](https://github.com/run-llama/llama_index) | RAG-система для подключения любых источников данных | Поиск по корпоративной документации компании |
| 33 | **AutoGen** | [microsoft/autogen](https://github.com/microsoft/autogen) | Мультиагентная платформа от Microsoft | Сложные сценарии совместного решения задач |
| 34 | **Dify** | [langgenius/dify](https://github.com/langgenius/dify) | Визуальный конструктор LLM-приложений и плагинов | Быстрое создание бэкенда для Action без кода |
| 35 | **Flowise** | [FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise) | Drag-and-drop интерфейс для создания агентов | Визуальное проектирование логики для Actions |

---

## 6. Финансы, рынки и ончейн-аналитика

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 36 | **CCXT** | [ccxt/ccxt](https://github.com/ccxt/ccxt) | Подключение к 100+ криптобиржам (Binance, Bybit, OKX) | Получение тикеров, стаканов и арбитраж |
| 37 | **CoinGecko API** | [man-c/pycoingecko](https://github.com/man-c/pycoingecko) | Котировки, объёмы и рейтинги 10 000+ криптовалют | Рыночная сводка и расчет капитализации |
| 38 | **YFinance** | [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | Доступ к данным акций, валют и индексов Yahoo Finance | Финансовый анализ акций Apple, Tesla, S&P 500 |
| 39 | **Web3.py** | [ethereum/web3.py](https://github.com/ethereum/web3.py) | Python-библиотека для работы с блокчейном Ethereum | Проверка смарт-контрактов, балансов и газа |
| 40 | **TonPy / TonWeb** | [toncenter/ton-python](https://github.com/toncenter) | Взаимодействие с блокчейном The Open Network (TON) | Отслеживание транзакций и жетонов в сети TON |
| 41 | **Solana-py** | [michaelhly/solana-py](https://github.com/michaelhly/solana-py) | Клиент для блокчейна Solana | Анализ транзакций и токенов на DEX Raydium/Pump |
| 42 | **DefiLlama API** | [DefiLlama/defillama-server](https://github.com/DefiLlama) | Крупнейший агрегатор метрик DeFi (TVL, доходность) | Анализ безопасности и доходности протоколов |

---

## 7. Безопасность, валидация и мониторинг

| # | Название | Ссылка на GitHub | Описание | Кейс для ChatGPT |
|---|---|---|---|---|
| 43 | **Pydantic** | [pydantic/pydantic](https://github.com/pydantic/pydantic) | Валидация структур данных в Python | Гарантия правильности JSON-ответов сервера |
| 44 | **Guardrails AI** | [guardrails-ai/guardrails](https://github.com/guardrails-ai/guardrails) | Защита ответов модели от галлюцинаций и утечек | Защита Action от инъекций промптов (Prompt Injection) |
| 45 | **Promptfoo** | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | CLI-инструмент для тестирования промптов и tool-вызовов | Автоматическое тестирование надежности экшенов |
| 46 | **Langfuse** | [langfuse/langfuse](https://github.com/langfuse/langfuse) | Опенсорсный трейсинг и аналитика для LLM | Логирование ошибок и задержек вызовов Action |
| 47 | **LiteLLM** | [BerriAI/litellm](https://github.com/BerriAI/litellm) | Универсальный прокси для вызовов 100+ языковых моделей | Резервный бэкенд на случай недоступности OpenAI |
| 48 | **Instructor** | [jxnl/instructor](https://github.com/jxnl/instructor) | Структурированные ответы через Pydantic | Строгий формат данных при общении модели с API |
| 49 | **Uvicorn** | [encode/uvicorn](https://github.com/encode/uvicorn) | Молниеносный ASGI-сервер для Python | Запуск сервиса на production-серверах |
| 50 | **Ngrok / Cloudflared** | [cloudflare/cloudflared](https://github.com/cloudflare/cloudflared) | Бесплатный защищенный туннель наружу для локального ПК | Тестирование Action прямо со своего компьютера без белого IP |
