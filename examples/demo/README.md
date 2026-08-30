# Ejemplo demo

Este ejemplo es la forma corta de probar AiKit con varios servicios de dominio. Sirve para dos
cosas: comprobar que el entorno arranca y tener a mano servicios sencillos que copiar o adaptar.

## Ejecución

```bash
./run.sh
```

El servicio queda disponible en el puerto 8000. Puedes probarlo con una petición sencilla:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "que hay en el trastero?"}'
```

El guion de arranque hace el trabajo pesado: añade el directorio del ejemplo a `PYTHONPATH`, fija
`AIKIT_CONFIG` y genera una clave de firma de sesión para desarrollo.

## Servicios incluidos

- `stock`: inventario en memoria de objetos guardados por ubicación. Es el más sencillo; empieza
  por aquí si quieres entender el contrato sin ruido.
- `users`: listado de usuarios con créditos, con un método que modifica el estado.
- `music`: control de un reproductor Mopidy. Es el más extenso y muestra un servicio que se
  comunica con un sistema externo.

Ninguno forma parte del _framework_: son ejemplos de lo que aportaría una aplicación real. Puedes
copiarlos, adaptarlos o quitarlos del `aikit.yaml` si no los necesitas.

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
