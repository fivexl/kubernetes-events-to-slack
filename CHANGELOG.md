### 1.5.2

* Better handling of event parsing erros - will send more details including stack trace and event itself
* Handle situation when there is no time stamp info in the event
* Wait only 30 sec after running into error
* Added terraform deployment example
* Fixed k8s deployment example - missed to specify service account name, remove hardcoded namespace

### 1.5.1

* Wait for 60 sec in case of failure to stream events before trying again. Useful in case of authorization issues, so the streamer does not spam the channel

### 1.5.0

* Changes in the default behavior of K8S_EVENTS_STREAMER_NAMESPACE. Before this version, if not specified, then would stream only events from the default namespace. From this version, the streamer would stream events from all namespaces.