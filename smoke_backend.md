Smoke-тесты (по порядку)
	1.	/health (или эквивалент) — сервис жив.
	2.	Sheets auth: дерни эндпоинт, который читает лист (например GET /api/jobs или get_all_jobs).
	•	Ожидаем: 200 + список строк (пусть даже пустой).
	3.	Worksheet правильный: убедись, что читает именно Pipeline, а не sheet1.
	4.	Дубликаты: два раза добавь одну и ту же вакансию разным регистром (Company vs COMPANY).
	•	Ожидаем: второй раз не добавляется / возвращает “duplicate”.
	5.	URL parsing: скоринг по URL (передай тестовый URL).
	•	Ожидаем: достал текст, сделал scoring в формате COMPANY/ROLE/STOP_FLAGS/ROLE_FIT.
	6.	Запись в Sheets: scoring→add_row реально добавляет строку в Pipeline и после этого POST /api/jobs/refresh сбрасывает кэш.
