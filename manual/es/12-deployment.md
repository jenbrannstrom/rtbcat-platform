# Capítulo 12: Despliegue

*Audiencia: DevOps, ingenieros de plataforma*

## Pipeline de CI/CD

```
Push to unified-platform
         │
         ▼
build-and-push.yml (automatic)
  ├── Run contract & recovery tests
  ├── Build API image
  ├── Build Dashboard image
  └── Push to Artifact Registry
         │
         ▼ (manual trigger)
deploy.yml (workflow_dispatch)
  ├── SSH into VM via IAP tunnel
  ├── git pull on VM
  ├── docker compose pull (prebuilt images)
  ├── docker compose up -d --force-recreate
  ├── Health check (60s wait + curl localhost:8000/health)
  └── Post-deploy contract check
```

### Por qué el despliegue es manual

El despliegue automático al hacer push fue deshabilitado tras un incidente en enero de 2026 en el que los despliegues automáticos competían con los despliegues manuales por SSH, corrompiendo contenedores y provocando pérdida de datos. El flujo de despliegue ahora requiere:

1. Activación manual a través de la interfaz de GitHub Actions ("Run workflow")
2. Selección explícita del entorno objetivo (staging o producción)
3. Escribir `DEPLOY` como confirmación
4. Campo opcional de motivo para la trazabilidad de auditoría

### Etiquetas de imágenes

Las imágenes se etiquetan con el SHA corto de git: `sha-XXXXXXX`. El paso de despliegue usa `GITHUB_SHA` para construir la etiqueta, de modo que la versión desplegada siempre corresponde a un commit específico.

## Cómo desplegar

1. Verificar que el build pasó: `gh run list --workflow=build-and-push.yml --limit=1`
2. Activar el despliegue:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Monitorear: `gh run watch <run_id> --exit-status`
4. Verificar: `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Verificación de un despliegue

El endpoint `/api/health` devuelve:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Compare `git_sha` con el commit que pretendía desplegar.

## Verificación de contratos post-despliegue

Después del despliegue, el flujo de trabajo ejecuta `scripts/contracts_check.py` dentro del contenedor de la API. Esto valida que los contratos de datos (reglas no negociables desde la importación hasta la salida de la API) se mantienen intactos. Si la verificación falla:

- Con `ALLOW_CONTRACT_FAILURE=false` (por defecto): el despliegue se marca como fallido.
- Con `ALLOW_CONTRACT_FAILURE=true` (bypass temporal): el despliegue se completa con una advertencia. Este bypass debe eliminarse tras la investigación.

## Staging vs. producción

| Entorno | Nombre de VM | Dominio |
|---------|-------------|---------|
| Staging | `catscan-vm` | (interno) |
| Producción | `catscan-vm` | `your-deployment.example.com` |

Despliegue primero en staging, verifique y luego despliegue en producción.

## Rollback

Para revertir, despliegue un commit anterior conocido como estable:

1. Identifique el último SHA correcto desde el historial de git o ejecuciones previas de despliegue.
2. Haga checkout de ese SHA en unified-platform (o use `--ref` con el commit).
3. Active el flujo de despliegue.

No existe un mecanismo de rollback dedicado. Simplemente se despliega una versión anterior.

## Relacionado

- [Visión general de la arquitectura](11-architecture.md): qué se despliega
- [Monitoreo de salud](13-health-monitoring.md): verificar que el despliegue funcionó
