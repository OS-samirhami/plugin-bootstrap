package com.plugin.exampleresourcemodelsource

import spock.lang.Specification
import org.rundeck.app.spi.Services
import org.rundeck.storage.api.Resource
import com.dtolabs.rundeck.core.storage.ResourceMeta
import com.dtolabs.rundeck.core.storage.keys.KeyStorageTree


class ExampleResourceModelSourceFactorySpec extends Specification {

    def "retrieve resource success"(){
        given:
        //TODO: set additional properties for your plugin
        Properties configuration = new Properties()
        configuration.put("tags","example")
        configuration.put("apiKeyPath","keys/api-key")

        def storageTree = Mock(KeyStorageTree)
        storageTree.getResource(_) >> Mock(Resource) {
            getContents() >> Mock(ResourceMeta) {
                writeContent(_) >> { args ->
                    args[0].write('password'.bytes)
                    return 6L
                }
            }
        }
        def services = Mock(Services) {
            getService(KeyStorageTree.class) >> storageTree
        }

        //def factory = new ExampleResourceModelSourceFactory()

        def vmList = ["node1","node2","node3"]

        when:
        // def result = factory.createResourceModelSource(services, configuration)
        ExampleResourceModelSource plugin = new ExampleResourceModelSource(configuration, services)
        def nodes = plugin.getNodes()

        then:
        nodes.size()==vmList.size()
    }


}