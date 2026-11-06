# Pruebas manuales RAG (iteración 5b)

Ejecutar con `OLLAMA_MODEL=llama3.2:latest make run-local` en una terminal. En Git Bash, en otra terminal, usar estos tres ejemplos **de dificultad creciente**. Cada prueba utiliza `--data-binary` para evitar errores de escape en Windows.

## 1. Una política: equipaje

```bash
printf '%s' '{"message":"¿Conservo el equipaje incluido si me reacomodan?","session_id":"rag-01","confirm_action":false}' > request.json
curl -sS -X POST http://localhost:8080/v1/chat -H 'Content-Type: application/json' --data-binary @request.json
```

Esperado: `BAGGAGE-001` en `citations`; respuesta sobre conservación del equipaje.

## 2. Dos políticas: equipaje y reembolso

```bash
printf '%s' '{"message":"Si me reacomodan por cancelación, ¿conservo equipaje y puedo pedir reembolso?","session_id":"rag-02","confirm_action":false}' > request.json
curl -sS -X POST http://localhost:8080/v1/chat -H 'Content-Type: application/json' --data-binary @request.json
```

Esperado: `BAGGAGE-001` y `REFUND-001` en `citations`; cobertura de ambos asuntos.

## 3. Tres políticas y consulta larga: equipaje, reembolso y prioridad

```bash
printf '%s' '{"message":"Si me reacomodan por cancelación, ¿conservo equipaje y puedo pedir reembolso? También quiero saber qué prioridad tengo como GOLD.","session_id":"rag-03","confirm_action":false}' > request.json
curl -sS -X POST http://localhost:8080/v1/chat -H 'Content-Type: application/json' --data-binary @request.json
```

Esperado: `BAGGAGE-001`, `REFUND-001` y `LOYALTY-001`. La prioridad depende de políticas; no se deben inventar cupos ni beneficios.

## Evaluación automática

```bash
make test
make evaluate-rag
python -m scripts.evaluate_rag --base-url http://127.0.0.1:8080
make evaluate-public
```

`evaluate_rag` presenta métricas agregadas y una entrada `cases` por pregunta con `question_type`, documentos recuperados/faltantes y cobertura temática (esta última solo cuando se consulta la API). **La cobertura basada en términos no es una evaluación semántica ni una garantía de faithfulness.**

## Presupuesto de contexto

`RAG_MAX_DOCS` (predeterminado: 5) y `RAG_CONTEXT_MAX_CHARS` (predeterminado: 6000) limitan el número y tamaño estimado de evidencias a enviar al LLM. El cálculo usa caracteres como aproximación conservadora; no sustituye el conteo del tokenizer de cada proveedor. El contrato ya limita `message` a 4000 caracteres. Si el contexto no cabe, el sistema omite fragmentos enteros en lugar de truncar una evidencia citada.
