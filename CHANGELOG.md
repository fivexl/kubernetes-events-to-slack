### 1.5.0

* Changes in the default behavior of K8S_EVENTS_STREAMER_NAMESPACE. Before this version, if not specified, then would stream only events from the default namespace. From this version, the streamer would stream events from all namespaces.