export type WorkerTaskType =
    | 'dataPreprocess'
    | 'samplingOptimize'
    | 'routePlan'
    | 'krigingPreview';

export type WorkerTaskPriority = 'urgent' | 'high' | 'normal' | 'low';

export interface WorkerTaskEnvelope<TPayload = unknown> {
    channel: 'task';
    id: string;
    type: WorkerTaskType;
    payload: TPayload;
}

export interface WorkerCancelEnvelope {
    channel: 'cancel';
    id: string;
}

export type WorkerIncomingMessage<TPayload = unknown> =
    | WorkerTaskEnvelope<TPayload>
    | WorkerCancelEnvelope;

export interface WorkerProgressMessage {
    id: string;
    kind: 'progress';
    progress: number;
    message?: string;
}

export interface WorkerResultMessage<TResult = unknown> {
    id: string;
    kind: 'result';
    result: TResult;
}

export interface WorkerErrorMessage {
    id: string;
    kind: 'error';
    error: string;
}

export type WorkerOutgoingMessage<TResult = unknown> =
    | WorkerProgressMessage
    | WorkerResultMessage<TResult>
    | WorkerErrorMessage;

export interface WorkerTaskOptions {
    priority?: WorkerTaskPriority;
    onProgress?: (progress: number, message?: string) => void;
}
