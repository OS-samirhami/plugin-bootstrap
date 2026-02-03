package com.plugin.exampleworkflowstep

import com.dtolabs.rundeck.plugins.step.PluginStepContext
import com.dtolabs.rundeck.core.execution.workflow.steps.StepException
import com.dtolabs.rundeck.plugins.PluginLogger
import spock.lang.Specification

class ExampleWorkflowStepSpec extends Specification {

    def getContext(PluginLogger logger){
        Mock(PluginStepContext){
            getLogger()>>logger
        }
    }

    def "check Boolean parameter"(){

        given:

        def example = new ExampleWorkflowStep()
        def context = getContext(Mock(PluginLogger))
        def configuration = [example:"example123",exampleBoolean:"true"]

        when:
        example.executeStep(context,configuration)

        then:
        thrown StepException
    }

    def "run OK"(){

        given:

        def example = new ExampleWorkflowStep()
        def logger = Mock(PluginLogger)
        def context = getContext(logger)
        def configuration = [example:"example123",exampleBoolean:"false",exampleFreeSelect:"Beige"]

        when:
        example.executeStep(context,configuration)

        then:
        1 * logger.log(2, 'Example step configuration: {example=example123, exampleBoolean=false, exampleFreeSelect=Beige}')
    }

}