# Despliegue en GitHub y activación de los workflows

Cómo publicar el repositorio (privado) y activar la integración continua (`ci.yml`) y la ejecución semanal (`radar_semanal.yml`). Los comandos se ejecutan desde la carpeta del proyecto.

## 1. Crear el repositorio y publicar

**Opción A: desde la web**

1. En <https://github.com/new>, crea el repositorio `radar-burbujas-ia` con visibilidad **Private**, sin README, .gitignore ni licencia, porque el proyecto ya los tiene.
2. Publica:

   ```powershell
   git remote add origin https://github.com/<usuario>/radar-burbujas-ia.git
   git push -u origin main
   git push origin --tags
   ```

**Opción B: con GitHub CLI**

```powershell
gh auth login
gh repo create radar-burbujas-ia --private --source . --remote origin --push
git push origin --tags
```

## 2. Verificar la integración continua

En la pestaña **Actions**, el workflow **CI** corre solo después del push. Instala las dependencias y ejecuta `pytest`, incluida una corrida completa de `main.py --offline`. Debe terminar en verde en 3 a 5 minutos.

Si falla:
- **Instalar dependencias:** suele ser un problema temporal de red. Usa **Re-run jobs**.
- **Correr pruebas:** el log indica la prueba que falló. `tests/test_main.py` necesita `data/raw/precios_diarios.csv` y `data/processed/cv_bsadf.json` en el repositorio (`git ls-files data`).

## 3. Activar la ejecución semanal

1. Lánzala una vez a mano: **Actions → Radar semanal → Run workflow**. Debe terminar en verde y dejar un commit "Radar semanal: ejecución manual del AAAA-MM-DD" con el reporte, el log y los datos.
2. Si falla en el paso "Guardar reporte…" por permisos, entra a **Settings → Actions → General → Workflow permissions** y elige **Read and write permissions**.
3. Desde ahí, el workflow corre cada lunes a las 02:00 UTC. Con la primera corrida programada, el KPI de SLA pasa de DEFINIDO a MEDIDO (ver `docs/automatizacion.md`).

## 4. Accesos

Según `docs/gobernanza.md`:
- El dueño, el operador y soporte tienen escritura.
- Los evaluadores tienen lectura: **Settings → Collaborators → Add people**.
- El comité no necesita acceso al repositorio: recibe el reporte del operador.

## Notas para Windows

- Ubica el proyecto en una carpeta de **ruta corta**. Con rutas muy largas, el entorno virtual puede superar el límite de 260 caracteres de Windows y la instalación queda incompleta.
- Si la carpeta está sincronizada con un servicio de nube y bloquea archivos de `.git`, pausa la sincronización durante el `push`.
