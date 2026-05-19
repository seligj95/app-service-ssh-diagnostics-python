param name string
param location string = resourceGroup().location
param tags object = {}

param appServicePlanId string
param pythonVersion string = '3.14'
param applicationInsightsConnectionString string
param azureOpenAiEndpoint string
param azureOpenAiDeployment string

var appSettings = [
  { name: 'WEBSITES_PORT',                              value: '8000' }
  { name: 'ENABLE_ORYX_BUILD',                          value: 'true' }
  { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT',             value: 'true' }
  { name: 'PYTHONPATH',                                 value: '/home/site/wwwroot' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING',      value: applicationInsightsConnectionString }
  { name: 'ApplicationInsightsAgent_EXTENSION_VERSION', value: '~3' }
  { name: 'XDT_MicrosoftApplicationInsights_Mode',      value: 'recommended' }
  // The new Python SSH helper aliases read AZURE_AI_FOUNDRY_ENDPOINT + AZURE_AI_MODEL.
  // The app reads the same vars so that breaking one breaks both — which is the point of the demo.
  { name: 'AZURE_AI_FOUNDRY_ENDPOINT',                  value: azureOpenAiEndpoint }
  { name: 'AZURE_AI_MODEL',                             value: azureOpenAiDeployment }
]

resource web 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': 'web'
  })
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    reserved: true
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      alwaysOn: true
      ftpsState: 'FtpsOnly'
      // On Python 3.14+, App Service auto-detects FastAPI in main.py and starts
      // it with `gunicorn -k uvicorn_worker.UvicornWorker`. Explicit empty
      // appCommandLine clears any prior custom command so detection kicks in.
      appCommandLine: ''
      http20Enabled: true
      minTlsVersion: '1.2'
      healthCheckPath: '/health'
      appSettings: appSettings
    }
  }
}

output id string = web.id
output name string = web.name
output principalId string = web.identity.principalId
output uri string = 'https://${web.properties.defaultHostName}'
