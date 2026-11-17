# Лабораторна 9: Lanora у Google Cloud

Стан на 17 листопада 2026 року. Проєкт: `lanora-511019`, регіон `us-central1`.
Завдання: https://learn.ucu.edu.ua/mod/assign/view.php?id=158424
Дедлайн: 19 листопада 2026 року, 23:55 за Києвом.

Основне розгортання й демонстрації виконані. До остаточного закриття всіх вимог
залишилися скриншоти/збережені оцінки офіційних калькуляторів та перевірка billing
наступного дня. Нижче ці кроки не позначено виконаними.

## Посилання та відтворення

- Сайт: https://lanora-511019.web.app
- API: https://peach-api-lwunl4a43q-uc.a.run.app
- Код: https://github.com/yurleomel/OOAD_Lab2/tree/lab9-google-cloud
- Основний коміт реалізації: https://github.com/yurleomel/OOAD_Lab2/commit/5f8a43fe990e6ddf4ad2bea01379bb9b4bd1e864
- Історія доповнень і доказів: https://github.com/yurleomel/OOAD_Lab2/commits/lab9-google-cloud
- Looker Studio: https://datastudio.google.com/reporting/49eadb28-85bc-4337-a81b-4f262abd613d/page/TymDG

Looker-звіт приватний; його читабельний скриншот і конфігурацію джерела додано
до матеріалів. У ZIP є копія відстежуваного коду та точний коміт у `START_HERE.txt`.
Паролі, токени, Terraform state і облікові дані тестового акаунта не включено.

**Cloud SQL зупинено після перевірок.** Попереднє читання з БД підтверджене JSON
і скриншотом приватного вікна. Для нового живого показу потрібен старт БД через
перевірений Terraform-план. Зупинка БД пояснює, чому зараз операції з даними
на доступному Firebase-сайті можуть завершуватися помилкою.

## Архітектура, доступ та IaC

| Частина | Google Cloud | Відповідник AWS |
|---|---|---|
| Статичний frontend та HTTPS | Firebase Hosting | S3 + CloudFront |
| Контейнер API | Cloud Run, 1 vCPU, 512 MiB, min 0, max 1 | Lambda з контейнера |
| Образи | Artifact Registry | ECR |
| PostgreSQL | Cloud SQL `db-f1-micro`, 10 GB SSD | RDS PostgreSQL `db.t4g.micro`, 20 GB gp2 |
| Секрети | Secret Manager | Secrets Manager |
| SQL-аналітика | BigQuery | Athena |
| Пакетне перетворення | Dataflow | Glue-подібний ETL |
| Візуалізація | Looker Studio | BI над результатом Athena |
| OCR і генеративна модель | Vision API, Vertex Gemini | Відповідні AI-сервіси / Bedrock |

Автентифікація Cognito, AWS parser і reports залишені в AWS, як дозволяє завдання.
Для Firebase використано вхід email/password; Google sign-in і paste-parser приховані,
доки їхні AWS allowlist/callback налаштування не містять GCP origin.

Корені Terraform `gcp/` і `gcp/bootstrap/` відокремлено від AWS. HCP workspace
`peach-gcp` має окремий state від `peach-prod`. API керуються Terraform.
Використано окремі service accounts для Terraform, API і Dataflow; HCP отримує
короткоживучі credentials через WIF/OIDC, без завантаження JSON-ключів.
Для laptop використано короткоживучий токен авторизованого Google Cloud CLI.

Налаштовано бюджетне сповіщення USD 5. Це сповіщення, а не жорстка межа витрат.
Усі застосовані плани мали нуль delete-дій. Після демонстрацій план зупинки БД
містив 0 додавань, 1 зміну, 0 видалень. Ресурси й дані збережені.

Схему БД створено адитивним baseline, еквівалентним Alembic revision 0005;
історичні міграції, що прибирають структури або дані, не запускалися.
Завдання міграції `peach-migrate-q5qgt` і `alembic check` завершилися успішно.
Детальні рішення: `docs/adr/0009-google-cloud.md`; інструкція: `gcp/README.md`.

## Перевірка застосунку

На реальному API синтетичний Cognito-користувач пройшов автентифікацію.
Readiness із БД, створення задачі, список і читання за ID успішні; анонімний
запит отримав 401. Задача збережена в БД:
`d7739476-2e3d-42cf-a3d8-c1b7c47cd33e`.

У приватному вікні Chrome відкрито Firebase-сайт, виконано вхід, показано дошку;
після оновлення сторінки задача залишилася. Докази:
`records/core-read-proof.json` і `screenshots/04-gcp-board-private-window.png`.

Локальна інтеграційна перевірка PostgreSQL 17 підтвердила повторне безпечне
застосування baseline, збереження задачі, ізоляцію користувачів і 401 без авторизації.
Перевірки Terraform, guard проти видалень, контейнер, frontend build/typecheck/lint
та тести зміненого auth пройшли. Локальні контейнери зупинені й збережені.

## Прогноз вартості для чотирьох профілів

USD/місяць, 730 годин, on-demand, без податків і рекламних кредитів.
AWS: `us-east-1`, GCP: `us-central1`. Це розрахунок за перевіреними тарифами,
а не фактичний рахунок чи завершений експорт калькулятора.

| Профіль | Активні години | AWS | GCP: SQL увесь місяць | GCP: SQL лише активні години |
|---|---:|---:|---:|---:|
| Ніхто не користується | 0 | 14.43 | 9.45 | 9.08 |
| 10 демонстрацій по 2 години | 20 | 14.43 | 9.46 | 9.11 |
| 8 годин, 22 робочі дні | 176 | 14.43 | 9.59 | 9.31 |
| Безперервне навантаження | 730 | 14.76 | 18.59 | 18.59 |

Припущення: 1 API-запит/с у межах активних годин, 200 мс оплачуваного часу,
512 MiB пам'яті, Cloud Run 1 vCPU без перекриття запитів, відповідь 2 KiB до Європи.
Lambda ARM64; ліміти безкоштовних запитів/обчислень вважаються доступними для акаунта.
Безкоштовні квоти спільні й можуть бути вже використані іншими workloads.
Профіль 730 годин пораховано арифметично: навантажувальний тест не запускався.

AWS містить постійно ввімкнений фактичний RDS Single-AZ: 0.016/год + 20 GB gp2
по 0.115/GB-місяць. Додано один секрет 0.40, припущені 0.5 GB ECR, невеликий
S3-сайт і 10 тисяч S3 GET. CloudFront та logs у межах вільних квот; NAT немає.

GCP містить Cloud SQL 0.0105/год, 10 GB SSD за 1.70/місяць, припущений 1 GiB
backup за 0.08. Для зупиненої БД збережений public IPv4 оцінено в 0.01/год.
Cloud Run враховує 180 тисяч vCPU-с, 360 тисяч GiB-с і 2 млн запитів безоплатно.
Egress до Європи: 0.12/GiB; північноамериканську безкоштовну квоту не застосовано.
Firebase Hosting: 10 GB storage і 360 MB/day transfer; припускається, що трафік
статики нижчий за денну квоту. Image, секрет і logs також у вільних квотах.

Опційні reports/LLM workloads, cold starts, податки та burst CPU credits не включено.
Розміри фактичних артефактів: frontend 91 файл, 2.14 MiB без стиснення;
GCP registry 83.899 MB. Припущення ECR 0.5 GB не видається за виміряний рахунок.

За цих припущень GCP дешевший у перших трьох профілях. У безперервному профілі
дешевший AWS: Cloud Run виходить за квоту CPU, а Lambda залишається в квоті GB-с.
У спокійних профілях домінує БД; у busy GCP API коштує близько 8.55, DB compute
7.67. Зупинка tiny SQL за наявності idle IPv4 дає малу економію. Firestore прибрав би
постійну SQL/IP складову, але потребував би іншої моделі даних і підрахунку операцій.

Повна деталізація: `costs/four-profile-breakdown.json`, `costs/costs.py`,
`costs/cost_report.py`. Незавершена перевірка: офіційні калькулятори AWS/GCP.
Інструмент Chrome двічі завис під час підключення після підтвердження видимого
вікна; вигаданих calculator screenshot/estimate до матеріалів не додано.

Тарифи й калькулятори:
https://aws.amazon.com/rds/postgresql/pricing/
https://aws.amazon.com/lambda/pricing/
https://cloud.google.com/sql/pricing
https://cloud.google.com/run/pricing
https://firebase.google.com/pricing
https://calculator.aws/
https://cloud.google.com/products/calculator

## BigQuery, Looker Studio та OCR

BigQuery: public Shakespeare query, job
`lab9_words_989592b8da894837867ed2de890465a3`, US. Оброблено 3,781,873 bytes
(3.61 MiB), billed 10 MiB до безкоштовної квоти; dry-run і виконання з лімітом
100 MiB. Десять рядків записано `WRITE_EMPTY` у нову таблицю
`lanora-511019.lab9.shakespeare_top10`; наявні таблиці не перезаписувалися.
SQL: `inputs/bigquery.sql`; результат і job metadata: `records/bigquery-5d721cff.json`.

Looker Studio напряму читає цю таблицю. Графік: `corpus` по Y,
`SUM(total_words)` по X, спадання, 10 горизонтальних стовпчиків.
Hamlet: 32,446; Antony and Cleopatra: 27,310. Значення збігаються із SQL.
Поточний UI називає сервіс Data Studio / Центр даних і пояснює перейменування.

Vision OCR: один `TEXT_DETECTION` на синтетичному чеку; розпізнано
`LANORA TEST CAFE` та `TOTAL 3.50`. Збережено оригінальний PNG і повну відповідь API.
Скриншот показує їх у явно позначеному локальному viewer; це не скриншот Cloud
Console. Viewer не робить нового OCR-запиту й не підміняє текст відповіді.

Три обов'язкові скриншоти:
`01-bigquery-query-and-bytes.png`, `02-looker-studio-chart.png`,
`03-vision-ocr-input-and-result.png` у `screenshots/`.
BigQuery Console показує email власника, тому цей файл збережено для приватної
здачі в LMS і виключено з публічного Git.

## Dataflow та Gemini

Dataflow: batch template Google `GCS_Text_to_BigQuery`, job
`2026-11-17_05_01_10-8688510766657573056`. Один `e2-standard-2`, максимум один
worker, 30 GB disk; три синтетичні CSV-рядки. Виконання 13:01:12-13:05:07 UTC,
стан `JOB_STATE_DONE`. У таблиці `lanora-511019.lab9.dataflow_demo_a714f4b8abd5`
перевірено IDs 1-3, теми й суму 30 хвилин. Після виконання Compute instances порожній.
Вхідні CSV/schema/UDF збережені в `inputs/`, підтвердження в `records/`.

Vertex API: оригінальний system prompt `agenda-v2`, tool schema і український input 1
із Lab 6, reference date 2026-10-20. Модель `gemini-3.8-flash`, global, LOW thinking,
ліміт 1,024 output tokens; один function call `record_agenda`.

Окремо той самий текст запущено в браузерному Vertex AI Studio, який тепер
відкриває Agent Studio / Gemini Platform. Перший UI-run дав неправильну форму
полів і збережений як diagnostic. Для другого, у новій вкладці, JSON Schema
адаптовано до OpenAPI `parameters` інтерфейсу: inline refs і nullable поля.
Отриманий agenda пройшов оригінальний `ParsedAgenda` validator і точно збігся
з нормалізованим API-результатом. Обидва UI-run були короткі; API key і endpoint
не створювалися, grounding і code execution вимкнені.

| Однаковий Lab 6 input 1 | Правильні поля | Вигадані значення | Input/output tokens | Вартість запиту, USD |
|---|---:|---:|---|---|
| Збережений Claude Haiku 4.5 | 15/15 | 0 | 1,754 / 287 | 0.00319 |
| Vertex Gemini 3.8 Flash API | 15/15 | 0 | 798 / 173 | 0.002495 до credits |
| Gemini 3.8 Flash Studio, виправлена схема | 15/15 | 0 | UI не показав billing split | Точну не заявлено |

Успішні відповіді зберігають початок 2026-10-26 о 10:00 без UTC offset,
45 хвилин, три теми, порожні не вказані owner/minutes і дію Taras до 2026-10-23.
Це один fixture, а не загальний рейтинг моделей. Новий Bedrock-виклик не робився.

Ціна Gemini global: 1.50 / 7.50 за млн input/output tokens до промокредитів;
вступна ефективна ціна через credits back до 31.12.2026 - 0.75 / 3.75.
Для API це 0.0024945 до credits або 0.00124725 з ними. Джерело:
https://cloud.google.com/model-garden/pricing
Лічильник 631 у Studio не є usageMetadata і не використаний як точний billing split.
Prompt-gallery save залишився у стані Saving, тому збережений gallery URL не заявлено.
Локально є повний fixture, функція, результат і скриншот реального запуску.

## Завершення та вміст пакета

Cloud SQL: `STOPPED`, activation policy `NEVER`. Dataflow завершено, workers відсутні.
Диски, backups та idle public IPv4 залишаються; прогноз утримання зупиненої SQL
близько 9.08/місяць не дорівнює нулю. Ціль коротких тестів - до USD 1 без витрат
на тривале зберігання ресурсів; фактичний рахунок треба перевірити після затримки billing.
Veo, enterprise Looker і Airflow не розгорталися: у завданні це in-class демонстрації.

У папці пакета:

- `report/`: цей звіт, PDF, детальний звіт, ADR і runbook.
- `screenshots/`: BigQuery, Looker, OCR, приватна дошка, Studio.
- `records/`: оригінальні результати, metadata, перевірки, стан ресурсів.
- `inputs/`: SQL, чек, agenda fixture/schema, Dataflow CSV/schema/UDF.
- `costs/`: чотири профілі, деталізація, скрипти й calculator inputs.
- `logs/`: журнали build/deploy/migration/live check/stop.
- `source/`: ZIP відстежуваного коду, точний commit і локальний diff.
- `SHA256SUMS.txt`: контрольні суми файлів.

Перед остаточною здачею слід додати офіційні калькуляторні оцінки та 18 листопада
перевірити Billing Reports для `lanora-511019`, зберегти скриншот/експорт фактичних
витрат і переконатися, що SQL досі зупинений. До LMS нічого автоматично не надіслано.
Відеозапис не створювався; у пакеті є реальні скриншоти, JSON та журнали.
