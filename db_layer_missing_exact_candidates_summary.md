# DB Layer Missing Exact Candidates

- `generated_at`: `2026-05-06T10:00:01.955862Z`
- `source_db`: `keymanage_accounting`

## Entry Layer Note

Les `entry` ont ete controles a part. Ils remontent surtout des libelles de contrepartie / fournisseur, pas des vraies lignes article exploitables comme `article_source`.

## btp

- partitions: `['fr_bd_903252617', 'fr_bd_842785719', 'fr_bd_844858571', 'fr_bd_792041840', 'fr_bd_823981568', 'fr_bd_509118329', 'fr_bd_951421064', 'fr_bd_879788230', 'fr_bd_914837463']`
- invoice_forms_seen: `10797`
- invoice_forms_kept_after_dedup: `9278`
- duplicates_skipped: `1519`
- missing_exact_candidates: `0`
- entry_docs_seen: `37063`

Top `entry.label` observes:
- `605 | POINT.P` -> `267`
- `607 | LPN VOLAILLE` -> `213`
- `6257 | RESTO` -> `209`
- `60611 | CARBURANT` -> `150`
- `627 | Commission virement instantané émis` -> `133`

Aucun nouveau candidat exact propre detecte.

## boulangerie

- partitions: `['fr_bd_519665103', 'fr_bd_890233000', 'fr_bd_880517875', 'fr_bd_915197842']`
- invoice_forms_seen: `10060`
- invoice_forms_kept_after_dedup: `8446`
- duplicates_skipped: `1614`
- missing_exact_candidates: `0`
- entry_docs_seen: `112557`

Top `entry.label` observes:
- `627 | AGIOS` -> `1917`
- `607 | AVIGROS` -> `1453`
- `607 | MECARUNGIS` -> `1413`
- `607 | BBV` -> `1298`
- `627 | Services bancaires et assimilés` -> `511`

Aucun nouveau candidat exact propre detecte.

## transport

- partitions: `['fr_bd_839181104', 'fr_bd_888020088', 'fr_bd_831060876', 'fr_bd_890852403', 'fr_bd_904094349', 'fr_bd_922040506', 'fr_bd_844082156', 'fr_bd_840367817', 'fr_bd_979300076', 'fr_bd_950819938']`
- invoice_forms_seen: `4546`
- invoice_forms_kept_after_dedup: `3725`
- duplicates_skipped: `821`
- missing_exact_candidates: `0`
- entry_docs_seen: `20778`

Top `entry.label` observes:
- `6251 | RESTAURATION` -> `156`
- `6261 | BOUYGUE` -> `118`
- `60611 | CARBURANTS` -> `113`
- `6226 | QUI MANAGE` -> `59`
- `60613 | CARBURANT/CB` -> `59`

Aucun nouveau candidat exact propre detecte.

## restaurant

- partitions: `['fr_bd_891370595', 'fr_bd_952061570', 'fr_bd_929728467']`
- invoice_forms_seen: `4179`
- invoice_forms_kept_after_dedup: `3661`
- duplicates_skipped: `518`
- missing_exact_candidates: `0`
- entry_docs_seen: `13333`

Top `entry.label` observes:
- `601 | METRO FRANCE` -> `169`
- `6011 | AVIGROS` -> `101`
- `627 | COMC` -> `80`
- `601 | RUNGISAVIGROS` -> `51`
- `601 | MISU` -> `44`

Aucun nouveau candidat exact propre detecte.
