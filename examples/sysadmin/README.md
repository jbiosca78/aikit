# Asistente para administración de sistemas

Este ejemplo muestra AiKit fuera de una web: un cliente de terminal para administración de
sistemas. El asistente responde preguntas sobre el estado del servidor y propone comandos para
resolver tareas habituales.

La idea importante es que el núcleo no depende del tipo de cliente. Esta terminal consume la
misma API que el widget de chat web.

## Ejecución

En una terminal, el servicio:

```bash
./run.sh
```

En otra, el cliente:

```bash
../../aikit/ui/shell/aikit-shell
```

## Modos de uso

```bash
aikit-shell                                   # sesión interactiva
aikit-shell "cuánto espacio libre queda?"     # consulta puntual
aikit-shell "cómo busco ficheros grandes?"    # propone el comando
journalctl -u nginx | aikit-shell             # analiza la salida recibida
journalctl -u nginx | aikit-shell "resume los errores"
aikit-shell --ultimo                          # muestra el último comando sugerido
aikit-shell -c "cómo reinicio el servicio ssh?"   # copia el comando al portapapeles
```

Dentro de la sesión interactiva, `nueva` reinicia la conversación y `salir` la cierra.

## El asistente propone, el operador decide

Los comandos que sugiere el modelo se muestran resaltados y se guardan en
`~/.config/aikit/ultimo-comando`, pero **nunca se ejecutan solos**. La persona decide si los usa
después de revisarlos.

Esto es intencionado. Ejecutar directamente órdenes generadas por un modelo sería un riesgo de
seguridad difícil de acotar, sobre todo si el modelo está leyendo registros o salidas de comandos
que podrían influir en su respuesta.

## Servicio de consulta del sistema

`services/sistema.py` expone seis operaciones, todas de solo lectura:

| Operación | Descripción |
|---|---|
| `get_disk_usage` | Espacio ocupado y disponible por punto de montaje |
| `get_memory_usage` | Memoria total, usada y disponible, y carga media |
| `get_service_status` | Estado de una unidad de systemd |
| `list_files` | Listado de un directorio autorizado |
| `tail_file` | Últimas líneas de un fichero autorizado |
| `get_allowed_paths` | Directorios que el asistente puede consultar |

## Controles de seguridad

El servicio no ejecuta órdenes recibidas del modelo ni construye ninguna a partir de texto
libre. Cada método invoca una utilidad concreta con argumentos validados. Los controles
aplicados son:

- **Directorios autorizados.** Solo se consultan rutas dentro de los directorios indicados en
  `AIKIT_RUTAS_PERMITIDAS`, por defecto `/var/log` y `/etc`. Las rutas se resuelven antes de
  comprobarse, de modo que `../` no permite salir del ámbito permitido.
- **Ficheros excluidos.** Aunque residan en un directorio autorizado, se rechazan los ficheros
  que contienen credenciales o material criptográfico: `shadow`, `sudoers`, claves privadas,
  ficheros `.env` y los directorios `ssh`, `ssl`, `pki`, `secrets` y `private`. Tampoco
  aparecen en los listados.
- **Nombres de unidad validados.** El nombre de servicio debe ajustarse a una expresión
  regular restrictiva antes de consultarse, y se invoca `systemctl` con argumentos fijos, sin
  intérprete de órdenes.
- **Límites de volumen.** El número de líneas devueltas y el tamaño de los listados están
  acotados, para no volcar registros completos al modelo.
- **Escucha local.** El servicio se enlaza a `127.0.0.1`.

Ten en cuenta que el contenido de los registros llega al proveedor del modelo. En sistemas con
datos sensibles conviene valorar un modelo local mediante Ollama; cambiarlo requiere tocar solo
la configuración de motor en `aikit.yaml`.

## Documentación relacionada

- [Crear un servicio de dominio](../../docs/crear-un-servicio.md)
- [Configuración](../../docs/configuracion.md)
- [Problemas frecuentes](../../docs/problemas-frecuentes.md)
