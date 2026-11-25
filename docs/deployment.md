# Deploying ECOTHERM on Render

The GitHub repository is the source code; the public website is a separate Render deployment.

1. Push the project to `https://github.com/Manikandan2009/ECOTHERM`.
2. Sign in to [Render](https://render.com/), choose **New → Blueprint**, and connect the `Manikandan2009/ECOTHERM` repository.
3. Render reads `render.yaml` and creates the `ecotherm-api` and `ecotherm-dashboard` services. Wait for both deployments to finish.
4. Open `https://ecotherm-dashboard.onrender.com`. The API health check is at `https://ecotherm-api.onrender.com/health`.

The frontend is built with `VITE_API_BASE_URL`; the API allows the dashboard origin through `ECOTHERM_CORS_ORIGINS`. If Render assigns different service URLs, update these two values in the respective service settings and redeploy.

## Cached data

The application uses local files under `data/cache`, and these files are excluded from Git. A new Render deployment therefore starts without the data cached on a developer's computer. The API can start, but cached-data dashboard features will be unavailable until the data is provisioned to the deployed service. Do not commit credentials or large/private cache files to GitHub. Configure appropriate persistent storage and securely restore the cache before expecting the deployed dashboard to show the local data.
