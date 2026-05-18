param name string
param location string = resourceGroup().location
param tags object = {}

@description('SKU name. P0v3 is a sensible default for a real demo; B1 also works.')
param skuName string = 'P0v3'

@description('Number of instances to run in parallel')
@minValue(1)
@maxValue(3)
param instanceCount int = 1

param reserved bool = true

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: instanceCount
  }
  properties: {
    reserved: reserved
  }
}

output id string = appServicePlan.id
output name string = appServicePlan.name
