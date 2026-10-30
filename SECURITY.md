# Política de seguridad

## Versiones con soporte

Solo la versión más reciente de la rama `main` recibe correcciones.

## Reportar una vulnerabilidad

No abras un issue público para reportar una vulnerabilidad. Escribe al autor por correo
(paultinoterronespuchuri@gmail.com) con:

- una descripción del problema y su impacto,
- los pasos para reproducirlo,
- la versión o el commit afectado.

Responderemos en un plazo razonable para confirmar la recepción y acordar la corrección.

## Alcance

Esta aplicación está pensada para usarse en una sola computadora. Son especialmente
relevantes los problemas que permitan:

- acceder a la API desde otra máquina o desde una página web ajena,
- leer o modificar datos sin la clave configurada,
- ejecutar código o escribir archivos fuera del directorio de datos.

Los datos se guardan en un archivo SQLite sin cifrar. Cifrar el archivo es responsabilidad
de quien lo despliega.
