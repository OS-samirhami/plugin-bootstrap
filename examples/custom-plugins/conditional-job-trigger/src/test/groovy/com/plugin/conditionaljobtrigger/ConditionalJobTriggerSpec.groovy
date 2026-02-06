package com.plugin.conditionaljobtrigger

import spock.lang.Specification
import com.dtolabs.rundeck.plugins.step.PluginStepContext
import com.dtolabs.rundeck.core.execution.ExecutionContext
import com.dtolabs.rundeck.core.execution.ExecutionListener
import com.dtolabs.rundeck.core.execution.workflow.OutputContext
import com.dtolabs.rundeck.core.data.DataContext
import com.dtolabs.rundeck.core.jobs.JobService
import com.dtolabs.rundeck.core.jobs.JobReference

/**
 * Basic tests for Conditional Job Trigger plugin
 */
class ConditionalJobTriggerSpec extends Specification {
    
    ConditionalJobTrigger plugin
    PluginStepContext mockContext
    ExecutionContext mockExecContext
    ExecutionListener mockLogger
    OutputContext mockOutputContext
    DataContext mockDataContext
    JobService mockJobService
    
    def setup() {
        plugin = new ConditionalJobTrigger()
        
        // Setup mock context
        mockContext = Mock(PluginStepContext)
        mockExecContext = Mock(ExecutionContext)
        mockLogger = Mock(ExecutionListener)
        mockOutputContext = Mock(OutputContext)
        mockDataContext = Mock(DataContext)
        mockJobService = Mock(JobService)
        
        mockContext.getExecutionContext() >> mockExecContext
        mockContext.getFrameworkProject() >> "test-project"
        mockExecContext.getExecutionListener() >> mockLogger
        mockExecContext.getOutputContext() >> mockOutputContext
        mockExecContext.getDataContext() >> mockDataContext
        mockExecContext.getJobService() >> mockJobService
        mockExecContext.getUser() >> "test-user"
    }
    
    def "plugin has correct name and service type"() {
        expect:
        ConditionalJobTrigger.PLUGIN_NAME == "conditional-job-trigger"
        ConditionalJobTrigger.PLUGIN_TITLE == "Conditional Job Trigger"
    }
    
    def "plugin properties are defined"() {
        when:
        plugin.targetJobId = "test-job-id"
        plugin.valueExpression = "true"
        plugin.conditionExpression = "false"
        plugin.matchValue = "prod"
        plugin.waitForCompletion = "true"
        plugin.failOnTargetFailure = "false"
        
        then:
        plugin.targetJobId == "test-job-id"
        plugin.valueExpression == "true"
        plugin.conditionExpression == "false"
        plugin.matchValue == "prod"
        plugin.waitForCompletion == "true"
        plugin.failOnTargetFailure == "false"
    }
    
    def "evaluateExpression returns boolean type"() {
        given:
        mockDataContext.replaceDataReferences("true") >> "true"
        
        when:
        def result = plugin.evaluateExpression("true", mockContext, mockLogger)
        
        then:
        result.value == true
        result.type == "boolean"
    }
    
    def "evaluateExpression returns string type"() {
        given:
        mockDataContext.replaceDataReferences("production") >> "production"
        
        when:
        def result = plugin.evaluateExpression("production", mockContext, mockLogger)
        
        then:
        result.value == "production"
        result.type == "string"
    }
    
    def "evaluateExpression returns number type"() {
        given:
        mockDataContext.replaceDataReferences("42") >> "42"
        
        when:
        def result = plugin.evaluateExpression("42", mockContext, mockLogger)
        
        then:
        result.value == 42L
        result.type == "number"
    }
    
    def "evaluateExpression returns null for empty"() {
        given:
        mockDataContext.replaceDataReferences("") >> ""
        
        when:
        def result = plugin.evaluateExpression("", mockContext, mockLogger)
        
        then:
        result.value == null
        result.type == "null"
    }
    
    def "shouldTriggerJob with null value returns false"() {
        expect:
        plugin.shouldTriggerJob(null, null, mockLogger) == false
    }
    
    def "shouldTriggerJob with boolean true returns true"() {
        expect:
        plugin.shouldTriggerJob(true, null, mockLogger) == true
    }
    
    def "shouldTriggerJob with boolean false returns false"() {
        expect:
        plugin.shouldTriggerJob(false, null, mockLogger) == false
    }
    
    def "shouldTriggerJob with non-empty string returns true"() {
        expect:
        plugin.shouldTriggerJob("production", null, mockLogger) == true
    }
    
    def "shouldTriggerJob with empty string returns false"() {
        expect:
        plugin.shouldTriggerJob("", null, mockLogger) == false
    }
    
    def "shouldTriggerJob with non-zero number returns true"() {
        expect:
        plugin.shouldTriggerJob(42, null, mockLogger) == true
        plugin.shouldTriggerJob(-1, null, mockLogger) == true
    }
    
    def "shouldTriggerJob with zero returns false"() {
        expect:
        plugin.shouldTriggerJob(0, null, mockLogger) == false
        plugin.shouldTriggerJob(0.0, null, mockLogger) == false
    }
    
    def "shouldTriggerJob with matchValue does exact comparison"() {
        expect:
        plugin.shouldTriggerJob("production", "production", mockLogger) == true
        plugin.shouldTriggerJob("staging", "production", mockLogger) == false
        plugin.shouldTriggerJob(42, "42", mockLogger) == true
    }
    
    def "execution skips when value is null"() {
        given:
        plugin.targetJobId = "test-job"
        plugin.valueExpression = ""
        mockDataContext.replaceDataReferences("") >> ""
        
        when:
        plugin.executeStep(mockContext, [:])
        
        then:
        1 * mockOutputContext.addOutput("conditional-trigger", "skipped", "true")
        1 * mockOutputContext.addOutput("conditional-trigger", "evaluated-value", "null")
        1 * mockOutputContext.addOutput("conditional-trigger", "value-type", "null")
    }
    
    def "execution skips when value is empty string"() {
        given:
        plugin.targetJobId = "test-job"
        plugin.valueExpression = ""
        mockDataContext.replaceDataReferences("") >> ""
        
        when:
        plugin.executeStep(mockContext, [:])
        
        then:
        1 * mockOutputContext.addOutput("conditional-trigger", "skipped", "true")
    }
    
    def "backward compatibility with conditionExpression"() {
        given:
        plugin.targetJobId = "test-job"
        plugin.conditionExpression = "false"
        plugin.valueExpression = null
        mockDataContext.replaceDataReferences("false") >> "false"
        
        when:
        plugin.executeStep(mockContext, [:])
        
        then:
        1 * mockOutputContext.addOutput("conditional-trigger", "skipped", "true")
    }
    
    def "plugin metadata is correct"() {
        expect:
        plugin.PLUGIN_NAME == "conditional-job-trigger"
        plugin.PLUGIN_DESCRIPTION.contains("Conditionally trigger")
    }
}
