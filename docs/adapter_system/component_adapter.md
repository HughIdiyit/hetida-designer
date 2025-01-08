# Component Adapter

The component adapter allows to write components that act as data sources or sinks.

This enables the addition of data sources / sinks during running operation of hetida designer without the need to write and deploy a new adapter. At the same time it keeps the decoupling and reproducibility provided by the hd adapter system in contrast to running such a data in/egestion component as an operator in a workflow.

The component inputs become (free text) filters and the component code may interact with external systems to obtain or send data.

**Advantages**:
* on-the-fly / ad-hoc: I.e. compared to "true" separate adapters, there is no deployment step necessary for adding additional data sources/sinks
* Versus accessing external data directly in a workflow (e.g. by using such a component as operator): 
  * Keep the decoupling between analytics / Data Science and Data Engineering tasks.
  * Reproducibility

**Disadvantages**:
* no business/use case specific hierarchical structure. May lead to reduced discoverability
  * note: can be partially alleviated by the [virtual structure adapter](./virtual_structure_adapter.md).
* efficiency: Ordinary adapters may handle all wirings to sources/sinks of the same adapter together in one invocation. Component adapter sources/sinks are handled sequentially and separately.
* security vs separate (generic rest) adapters: Typically accessing external systems requires credentials. Such credentials must be available in the runtime service for the component adapter.

## Configuration

### Basic Configuration
Configuration can be set via an env file which must be configured via the `HD_COMPONENT_ADAPTER_ENVIRONMENT_FILE` environment variable.

Additionally environment variables can be set directly (overriding possible settings from an env file).

Note that some configuration options have to be set for the hetida designer backend service, where the compinent adapter's webservice runs. Others have to be set for the hetida designer runtime service where the adapter data fetching/sending is actually invoked during execution.

### Adapter Activation
`COMPONENT_ADAPTER_ACTIVE` (default `true`) determines whether the adapter is active. In particular that activates its webservice as part of the hetida designer backend.

### Adapter Registration
The adapter must be correctly registered according to [adapter registration](./adapter_registration.md). Its adapter key is `component-adapter`. Note again that its external url has to point to the hetida designer backend service in order to reach its webservice. Its internal url is not used.

Example of its part if `HETIDA_DESIGNER_ADAPTERS`:
```
component-adapter|Component Adapter|http://localhost:8080/adapters/component|http://localhost:8080/adapters/component
```

### Configuration options

* `COMPONENT_ADAPTER_ALLOW_DRAFT_COMPONENTS` (default: `false`): Whether components in Draft state are allowed to be used as component sources/sinks. Released Components can always be selected and deprecated/disabled components can still be used in wirings but can not be selected in the hetida designer user interface.
* `COMPONENT_ADAPTER_ALLOWED_SOURCE_CATEGORIES` (default: `null`): A (json) array of allowed categories for components that can act as sources. The default `null`does not impose any restrictions.
* `COMPONENT_ADAPTER_ALLOWED_SINK_CATEGORIES` (default: `null`): A (json) array of allowed categories for components that can act as sinks. The default `null`does not impose any restrictions.

## Usage

## Source Components
TODO:
* allowed inputs / outputs for sources
* example

## Sink Components
TODO:
* allowed inputs / outputs for sinks
* example?
