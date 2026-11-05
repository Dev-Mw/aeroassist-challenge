---
doc_id: IRROPS-001
title: Reacomodación por disrupciones
version: 1.2
updated: 2026-07-15
synthetic: true
---

# Reacomodación por disrupciones

> Documento sintético creado solo para el challenge. No representa una política real.

## Cancelación

Ante un vuelo cancelado, el agente debe ofrecer primero la alternativa disponible más cercana para el mismo origen y destino. La reacomodación por cancelación no cobra penalidad ni diferencia de tarifa dentro de los tres días anteriores o posteriores a la fecha original.

El estado del vuelo y los cupos son dinámicos: siempre se consultan mediante las herramientas operacionales. Este documento no confirma que un vuelo esté cancelado ni que una alternativa tenga asientos.

## Confirmación

Buscar opciones es una acción de lectura. Crear un hold de reacomodación modifica estado y requiere confirmación explícita del solicitante. La confirmación debe referirse a la reserva y al vuelo alternativo de la conversación actual. Cada creación usa una clave de idempotencia.

## Causa de la disrupción

La reacomodación aplica tanto a causas controlables como no controlables. La asistencia material adicional depende de la causa y se consulta en `CARE-001`.

