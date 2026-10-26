/* Где группа — подключение к Supabase (живой режим).
   Пока url и key пустые, страница работает в демо-режиме: участники видят друг друга
   только во вкладках одного браузера, а «другие паломники» на карте ненастоящие.
   Как подключить: ИНСТРУКЦИЯ.md → «Живой режим». key — это публичный anon-ключ проекта. */
window.WHERE_CFG = {
  url: "https://xuqyowsurxmsddzljxdu.supabase.co",
  key: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh1cXlvd3N1cnhtc2RkemxqeGR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3OTE3MjUsImV4cCI6MjEwODM2NzcyNX0.oHSIhRlW6Ps6_aZ5vZpENauOzzbg80yF8o3m0gfq3qE",   // публичный anon-ключ (не service_role): защищён правилами RLS в supabase.sql
  trips: { "UMRA-0009": "2026-11-07" }   // последний день поездки по префиксу кода группы: после него страница перестаёт делиться местом, точки удаляются сами (pg_cron)
};
