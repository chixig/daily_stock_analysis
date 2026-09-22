# R1 field dependency and evidence semantics
| Field / path | event_time | available_at | Runtime role | Reliability / evidence role |
|---|---|---|---|---|
| S1_F1 daily previous CLV | previous close15:00 | previous close plus unknown vendor latency | preplanned sale condition; inherited arithmetic unchanged | daily OHLC source comparison only |
| S2_F2 cumulative CLV | current14:50 completed bars |14:50 plus unknown vendor latency | inherited sale condition, pending price-data verification | never add ex-post quality as a new filter |
| previous reference price / declared ex-dividend | before current opening | prior close / published action, exact feed latency unknown | current legal limit proxy; no current final H/L/V | original corporate-source limitations retained |
| current daily open | opening auction uncross09:25 |09:25 market event; feed latency unknown | opening fill-price / budget proxy; limit blocked => later opens retry | observed price != proven1000-share execution |
| 09:45 end-labelled bar OPEN | nominal interval start09:40, inferred end stamps | market09:40; stored full-bar retrieval09:45 or unknown | prescheduled09:40 price proxy ONLY; decision not based on bar final H/L/C/V | indicator-only; historical receipt/fill not certified; not claim deployable feed |
| current completed bar H/L/C/V | its end time |end+unknown receipt latency | legacy intraday replay only; none in new retry rule | may be inaccurate; flagged independently |
| daily final H/L/V/C and48-bar grid | current close15:00 or later | after15:00+unknown vendor delay | NOT part of new opening or09:40 window selection | retrospective audit / S2 quality attribution only |
| legacy path_strict_good | after current full day | after15:00+unknown delay | original replay allowed intraday window iff true (P1) | labelled ex-post; original records immutable |
| old suppressed intraday window | historical bar time | gate only knowable after15:00 | unknown whether a reliable fill existed; not automatically a real no-trade decision | suppression exposure, not proven lost profit |
| current closing price/limit |15:00 uncross |15:00+unknown delay | assesses preplanned sell's indicative fill; not used as pre-close decision | auction quantity unknown |
| cash / inventory / lots / dividend receivable | each model event | immediately after simulated event | determine self-financing quantity and T+1; no future QC | separately reconstructed accounting checks |
| qualified1m overlap | historical bar end; qualification afterfull day | researcher now | never gates original signals or revised account orders | B signal verification / C indicative price comparison only |
| missing/uncertified bar | no confirmed event/arrival | unknown | missing numeric price => no observed fill, retain deficit; uncertain existing numeric price => explicit indicative scenario | no silent zero loss, no automatic reliability claim |

New open-only rule removes any dependency on current final daily volume at opening. A positive daily close/volume can still assess the closing execution after15:00; it never changes earlier opening orders. Prefix checks stop before the closing event. Quote data availability and queue capacity remain unknown; causal model checks do not certify them.
