# Lab 9 evidence

Core implementation commit:
[5f8a43f](https://github.com/yurleomel/OOAD_Lab2/commit/5f8a43fe990e6ddf4ad2bea01379bb9b4bd1e864).
Further evidence is on branch `lab9-google-cloud`. Full report: [docs/lab9.md](../../docs/lab9.md).

- Frontend: https://lanora-511019.web.app
- API: https://peach-api-lwunl4a43q-uc.a.run.app
- Database read/authentication: [core-read-proof.json](core-read-proof.json).
- Real private-window board: [gcp-board-private-window.png](gcp-board-private-window.png).
- BigQuery SQL, ten rows, processed/billed bytes: [bigquery-5d721cff.json](bigquery-5d721cff.json).
- Looker Studio chart: [looker-studio-bigquery-chart.png](looker-studio-bigquery-chart.png),
  [report/source manifest](looker-studio.json).
- Vision input: [synthetic receipt](synthetic-receipt-ea77eb7d.png);
  [actual response](vision-ocr-dfdc251e.json); [local viewer](vision-ocr-evidence.html).
- Dataflow completed and its three output rows were checked:
  [dataflow-verified-e2dbab92.json](dataflow-verified-e2dbab92.json).
- Vertex Gemini API result with the real Lab 6 prompt and schema:
  [gemini-agenda-a24ac7c3.json](gemini-agenda-a24ac7c3.json).
- Four-profile cost inputs, component sums and estimates:
  [cost-breakdown-2026-11-17.json](cost-breakdown-2026-11-17.json).
- Retained resources stopped: [stopped-resources-7550da17.json](stopped-resources-7550da17.json).

Cloud SQL is intentionally stopped. A new live database read needs a reviewed start plan;
the previous successful read and retained task are documented above. Disk, backups and idle
public IPv4 can still bill. All artifacts, accounts and task data are retained.

Still pending: final BigQuery/OCR screenshots, the Vertex AI Studio UI step, official calculator
estimates and a next-day billing check. The CLI JSON responses are not presented as screenshots
or as proof that a separate UI step was completed. This directory is not yet a complete submission.
