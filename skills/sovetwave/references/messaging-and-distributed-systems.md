# Messaging and distributed systems

Read this reference for message delivery, brokers, queues, asynchronous processing, or distributed-system terminology.

Use the role that the sentence actually describes. On first mention, explain a formal English term in Russian when it matters; preserve the formal name itself unchanged.

| English term | Sense or context | Prefer when the meaning fits |
|---|---|---|
| producer / consumer | generic message or data-flow roles | производитель / потребитель |
| sender / receiver | delivery of a specific message | отправитель / получатель |
| publisher / subscriber | publish/subscribe roles | издатель / подписчик |
| message broker | intermediary such as Kafka or RabbitMQ | брокер сообщений |
| transport | abstract delivery mechanism | транспорт сообщений / канал передачи |
| topic | Kafka-style named stream | топик |
| partition | Kafka-style partition | раздел |
| consumer group | messaging group | группа потребителей |
| payload | message contents | полезная нагрузка / содержимое сообщения |
| outbox | transactional outgoing-message store | таблица исходящих сообщений (`outbox`) on first mention |
| dead-letter queue | rejected-message destination | очередь необработанных сообщений (`DLQ`) on first mention |
| tenant | formal multi-tenant entity | организация, клиент, или область клиента; retain `tenant` only if it is a formal project term |

Keep formal names such as `KafkaProducer`, `KafkaConsumer`, `Producer API`, `ConsumerRecord`, `DLQ`, `TTL`, `message_id`, and `last-write-wins` exactly when they name a concrete API, field, or configured policy.

Bad: `producer → транспорт → consumer`.

Good: `производитель → брокер сообщений → потребитель`.

Good, when the component is not known: `отправитель → канал передачи → получатель`.
