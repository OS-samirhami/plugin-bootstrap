package com.plugin.exampleoption

import com.dtolabs.rundeck.plugins.step.PluginStepContext
import com.dtolabs.rundeck.core.execution.workflow.steps.StepException
import com.dtolabs.rundeck.plugins.PluginLogger
import spock.lang.Specification

class ExampleOptionSpec extends Specification {

    def getContext(PluginLogger logger){
        Mock(PluginStepContext){
            getLogger()>>logger
        }
    }

    def "get options"(){
        given:

        def example = new ExampleOption()
        def configuration = [example:"example123",exampleBoolean:"false",]

        when:
        def options = example.getOptionValues(configuration)

        then:
        options.size() > 0
    }


}