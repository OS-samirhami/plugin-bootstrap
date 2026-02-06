package com.plugin.conditionaljobtrigger

import com.dtolabs.rundeck.core.execution.workflow.steps.FailureReason

/**
 * Define failure reasons for the Conditional Job Trigger plugin
 */
enum PluginFailureReason implements FailureReason {
    JobServiceUnavailable,
    JobNotFound,
    JobExecutionFailed,
    ConditionEvaluationError
}
