---
status: review
---

# § 8.6. Отрицательные условия

## Открытие

Условия бывают двух родов, и разница между ними — не грамматическая.

```запрос,песочница
ВЫБРАТЬ
    Товары.Наименование
ИЗ
    Справочник.Товары КАК Товары
ГДЕ
    Товары.Артикул = "БУМ-А4"
```

[▶ Выполнить в песочнице](https://imiron.ru/BSLexicon/query/?gzq=H4sIAAAAAAAC_22OOw6CUBBF-7eKF3qpbN0bwcKC5vELhmgiWkpBSEiI8tnCmR0xSiOJ09zJnZtzh4QnMTccd2pjdXSZaGkkkMjnSkPPQMe42qo9neFMscYrZgnUb5nk9L2-_F-GpVR6ueEaUjLyP31OJfww5MjbHqyn3z247HB7bwHASNNhrQAAAA&schema-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.schema.yaml&data-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.data.yaml&source=https%3A%2F%2Fimiron.ru%2F1c-reading-queries%2Fchapters%2F08_proektirovanie_pod_bystruyu_vyborku%2F08-06_otricatelnye_usloviya.html&title=%C2%A7+8.6.+%D0%9E%D1%82%D1%80%D0%B8%D1%86%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D0%B5+%D1%83%D1%81%D0%BB%D0%BE%D0%B2%D0%B8%D1%8F)

```запрос,песочница
ВЫБРАТЬ
    Товары.Наименование
ИЗ
    Справочник.Товары КАК Товары
ГДЕ
    Товары.Артикул <> "БУМ-А4"
```

[▶ Выполнить в песочнице](https://imiron.ru/BSLexicon/query/?gzq=H4sIAAAAAAAC_22OMQ6CUBBE-3-KH3qoLI1nI1BY2HwVIiGQCJZaEBISooJXeHsjFmg0cZvZzE7eLCfuHLniqHkYq6PLSEsjoRwCShp63nQMq63a0xkyLmu84iOh-i2j7JfrM_hmWHKl5z9cw5mE9E-fU4lmhsS87HZnPX3vRuHjNt4E4Fh0dq4AAAA&schema-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.schema.yaml&data-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.data.yaml&source=https%3A%2F%2Fimiron.ru%2F1c-reading-queries%2Fchapters%2F08_proektirovanie_pod_bystruyu_vyborku%2F08-06_otricatelnye_usloviya.html&title=%C2%A7+8.6.+%D0%9E%D1%82%D1%80%D0%B8%D1%86%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D0%B5+%D1%83%D1%81%D0%BB%D0%BE%D0%B2%D0%B8%D1%8F)

Первое условие говорит, **что искать**. Второе — что **не** искать.

## Почему это не одно и то же

Указатель отвечает на вопрос «где строки с таким значением». Открыть его на
нужном месте можно, когда значение названо.

```текст
  = "БУМ-А4"     открыть указатель
                 на нужном месте

  <> "БУМ-А4"    нужное место — везде,
                 кроме одного
```

«Везде, кроме одного» — это и есть просмотр всей таблицы. Указатель тут не
помогает: подходящие строки разбросаны по всему диапазону.

То же верно для `НЕ В (…)`, для `НЕ ПОДОБНО`, для `<>` — для любого условия,
которое очерчивает не искомое, а исключаемое.

## Как переписывают

Замысел один: **сказать, что искать, вместо того что не искать.**

| было | стало |
|---|---|
| `Вид <> "Списание"` | `Вид В ("Продажа", "Возврат")` |
| `НЕ Проведён` | `Проведён = ЛОЖЬ` |
| `НЕ Товар В (…)` | соединение и отбор по несовпадению |

Первая строка — самая частая. Видов документа обычно немного, они известны, и
перечислить нужные проще, чем исключить один.

Вторая — про булево поле. Для реквизита `Проведён`, который у документа заполнен
всегда, эти два условия дают один ответ, но второе названо значением, а не
отрицанием. Для поля, которое бывает незаполненным, так рассуждать нельзя:
пустота ведёт себя не как `Ложь`, и это отдельный разговор.

Третья сложнее и заслуживает примера.

## Отбор по отсутствию

«Товары, которые ни разу не продавались» — условие по своей природе
отрицательное. Написать его через `НЕ В` можно:

```запрос,песочница
ВЫБРАТЬ
    Товары.Наименование
ИЗ
    Справочник.Товары КАК Товары
ГДЕ
    НЕ Товары.Ссылка В
        (ВЫБРАТЬ
            СтрокиРеализации.Товар
        ИЗ
            Документ.РеализацияТоваров.Товары КАК СтрокиРеализации)
```

[▶ Выполнить в песочнице](https://imiron.ru/BSLexicon/query/?gzq=H4sIAAAAAAAC_4WPwQqCUBBF936Fy9r4jWZQCxeVKYUgZNtaSCA9tOwXzvxRo4_MMmg2M8y7c969RJzYcGDNkbPjaunQcKEQX0KPjALDjZK7XWs3lA57dlae8xBf9xcaWXavlTdkuKRKTz-4DltiEgvISL4-zWUmITUVhUvUqdqaMHb7Kr0J1EajN0YFpRqqdboqcqHdDCz1d32GfhG3AJnbvBJ4Y5Ks3qC2_476x8z0CY25eWd3AQAA&schema-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.schema.yaml&data-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.data.yaml&source=https%3A%2F%2Fimiron.ru%2F1c-reading-queries%2Fchapters%2F08_proektirovanie_pod_bystruyu_vyborku%2F08-06_otricatelnye_usloviya.html&title=%C2%A7+8.6.+%D0%9E%D1%82%D1%80%D0%B8%D1%86%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D0%B5+%D1%83%D1%81%D0%BB%D0%BE%D0%B2%D0%B8%D1%8F)

А можно иначе: соединить с продажами и оставить те строки, где пары не нашлось.

```запрос,песочница
ВЫБРАТЬ
    Товары.Наименование
ИЗ
    Справочник.Товары КАК Товары
        ЛЕВОЕ СОЕДИНЕНИЕ
            (ВЫБРАТЬ РАЗЛИЧНЫЕ
                СтрокиРеализации.Товар КАК Товар
            ИЗ
                Документ.РеализацияТоваров.Товары КАК СтрокиРеализации)
            КАК Продажи
        ПО Товары.Ссылка = Продажи.Товар
ГДЕ
    Продажи.Товар ЕСТЬ NULL
```

[▶ Выполнить в песочнице](https://imiron.ru/BSLexicon/query/?gzq=H4sIAAAAAAAC_4WRMU7DQBREe59iS2h8A24QpeM-IUhQpABCrERBTmIaiqSwIgKWAXOF92_EeI0Sr0PENvP1d_7s_FnGrHlgxT3PbCKno6JiS24DG8Wk5BR8suOraQsLdhEzpg0949sG6m-p7NbflnFbwzGX-jzQ9ZN--omEMQuSWkjARMqpMBUme159zgjMOl9MpTDjRfR1h96Ys6HMVZSytdISOR-q3uXiRli0jB7bDNT2-wbNSS1t100-NoyP37C7g2CNf0fzj83z0Mrv0NKPvIr8RnFIdMmi84eZXdlIiiW5u-jMtfxEPGqhJsSTJKevyXz8_cte7wcPKxwtPwIAAA&schema-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.schema.yaml&data-src=https%3A%2F%2Fraw.githubusercontent.com%2FiMironRU%2F1c-reading-queries%2Fmain%2Fassets%2Fsandbox%2Fkanctovary.data.yaml&source=https%3A%2F%2Fimiron.ru%2F1c-reading-queries%2Fchapters%2F08_proektirovanie_pod_bystruyu_vyborku%2F08-06_otricatelnye_usloviya.html&title=%C2%A7+8.6.+%D0%9E%D1%82%D1%80%D0%B8%D1%86%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D0%B5+%D1%83%D1%81%D0%BB%D0%BE%D0%B2%D0%B8%D1%8F)

Ответ тот же. Но здесь работа устроена иначе: соединение ищет пары по указателю,
а отбор идёт уже по результату — по колонке, в которой пусто.

Приём стоит запомнить: **отсутствие ищут левым соединением и проверкой на
пустоту.**

## Не всякое отрицание переписывают

Мера здесь та же, что и везде в главе.

Если отрицание отсекает малую часть данных — скажем, одну строку из
справочника, — переписывать нечего: просмотр всё равно случится, а условие
понятнее в исходном виде.

Переписывают тогда, когда **отрицание стоит на пути к большой таблице** и мешает
воспользоваться указателем.

## Что это меняет для чтения

В каждом условии смотрят на одно: названо ли искомое значение.

- `=`, `В (…)`, `МЕЖДУ` — названо, указатель годится;
- `<>`, `НЕ В (…)`, `НЕ ПОДОБНО` — не названо, будет просмотр;
- `ЕСТЬ NULL` после левого соединения — отдельный приём, а не отрицание.

## Главное

Условие, которое называет искомое значение, позволяет открыть указатель на
нужном месте; условие, которое называет исключаемое, — нет: подходящие строки
разбросаны, и остаётся просмотр всей таблицы. Поэтому `<>`, `НЕ В`, `НЕ ПОДОБНО`
переписывают на перечисление того, что нужно, а `НЕ Поле` — на сравнение со
значением. Отбор по отсутствию — «те, для кого пары нет» — делают левым
соединением и проверкой `ЕСТЬ NULL`. Мера прежняя: переписывают, когда отрицание
стоит на пути к большой таблице, а не ради самого правила.

---

*Приёмы разобраны поодиночке. Осталось сказать, какие из них дают большую часть
потерь — и с чего начинать, когда отчёт уже медленный.*

## Контрольные вопросы

1. Почему условие с `<>` не даёт воспользоваться указателем?
2. На что переписывают `Вид <> "Списание"`?
3. Чем `Проведён = ЛОЖЬ` лучше, чем `НЕ Проведён`?
4. Как ищут «те, для кого пары не нашлось»?
5. Когда отрицание переписывать не нужно?
6. Как отличить условие, которое годится для указателя?

## Упражнения

**Переверните условие.** Возьмите три отрицательных условия из своей базы и
перепишите их на положительные. Все ли поддались?

**Сравните два способа.** Выполните оба запроса про непроданные товары. Ответы
совпали?

**Найдите просмотр.** Просмотрите запросы своего отчёта и отметьте условия, из-за
которых указателем воспользоваться нельзя.
