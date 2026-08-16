# C++ lifetime and queue semantics

Read this reference for C++ ownership, lifetime, queues, waiting, or `std::string_view`.

Name the ownership property before naming the symptom. `std::string_view` is a formal type name; preserve it exactly. In Russian prose, call its generic role a «невладеющее строковое представление». If it refers to storage whose lifetime has ended, use «висячее строковое представление» or state literally that the representation refers to destroyed storage. Do not call the `std::string_view` itself a «ссылка», «указатель» or «вид»: it is neither a C++ reference nor a pointer, and those calques hide both the string and the ownership issue.

Do not call a queue or a `std::mutex`-using operation «неблокирующей» merely because `take()` returns immediately when it is empty. With a `std::mutex`, it is not lock-free; with no `std::condition_variable`, it simply does not wait for an element. State the exact property that matters: «извлечение не ожидает появления элемента», «попытка извлечения без ожидания появления элемента», «очередь не реализует ожидающее извлечение» or, when true, «очередь реализована без блокировок».

Treat waiting, the distinction between an empty queue and an empty payload, acknowledgement, and redelivery as contract questions unless a stated requirement makes them necessary. Their absence is a defect only when the required delivery semantics depend on them.

When repairing `std::string_view` with expired storage, require only a владеющий результат. Do not first require a separate representation of «очередь пуста». Mention `std::optional<std::string>` only conditionally: if the known contract permits an empty message and requires distinguishing it from an absent element; otherwise choose the API form after the contract is fixed.

Do not infer FIFO, no-loss or no-duplicate delivery, or multi-producer/multi-consumer support from the word «очередь» or from a current container implementation. A test that records current behaviour is a characterisation test and must not silently become an interface requirement.

When code contains no confirmed caller, handler, or end-to-end route, formulate the mandatory check narrowly: «воспроизвести и устранить дефект времени жизни». A correlation trace, successful handler processing, and behaviour after handler failure are applicable only when the route and delivery guarantee are part of the known contract. In a table, distinguish «подтверждённый дефект реализации» from «свойство, зависящее от контракта» rather than placing both under an unqualified «Дефект».
