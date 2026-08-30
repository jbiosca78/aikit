# Ejemplo demo

Integración mínima de AiKit con varios servicios de dominio. Sirve para comprobar que el entorno
funciona y como referencia de cómo se escribe un servicio.

## Ejecución

```bash
./run.sh
```

El servicio queda disponible en el puerto 8000. Para comprobarlo:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "que hay en el trastero?"}'
```

El guion de arranque añade el directorio del ejemplo a la ruta de búsqueda de Python, indica su
`aikit.yaml` mediante `AIKIT_CONFIG` y genera una clave de firma de sesión para el desarrollo.

## Servicios incluidos

- `stock`: inventario en memoria de objetos guardados por ubicación. Es el más sencillo y el
  mejor punto de partida para entender el contrato.
- `users`: listado de usuarios con créditos, con un método que modifica el estado.
- `music`: control de un reproductor Mopidy. Es el más extenso y muestra un servicio que se
  comunica con un sistema externo.

Ninguno forma parte del _framework_: son ejemplos de lo que aporta una aplicación. Pueden
copiarse y adaptarse, o eliminarse de la configuración si no interesan.

El servicio `music` requiere un servidor Mopidy accesible; si no se dispone de él, conviene
comentar su entrada en la sección `services` del `aikit.yaml`.

## Configuración

El fichero `aikit.yaml` de este directorio incluye, además de la selección de motor y servicios,
un ejemplo de la sección `rewrites`, que normaliza expresiones frecuentes del usuario antes de
enviarlas al modelo.

## Documentación relacionada

- [Crear un servicio de dominio](../../docs/crear-un-servicio.md)
- [Configuración](../../docs/configuracion.md)
- [Problemas frecuentes](../../docs/problemas-frecuentes.md)
