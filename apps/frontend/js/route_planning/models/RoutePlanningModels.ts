/**
 * 路径规划数据模型
 */

export interface SamplingPoint {
    id: string;
    name?: string;
    latitude: number;
    longitude: number;
    priority: number;
    timeWindowStart?: string;
    timeWindowEnd?: string;
    serviceTime: number;
    isReachable: boolean;
    metadata?: Record<string, any>;
}

export interface RouteSegment {
    fromPointId: string;
    toPointId: string;
    distance: number;
    duration: number;
    cost: number;
    geometry?: Record<string, any>;
    instructions?: string[];
}

export interface PlannedRoute {
    routeId: string;
    pointSequence: string[];
    segments: RouteSegment[];
    totalDistance: number;
    totalDuration: number;
    totalCost: number;
    startTime?: string;
    endTime?: string;
}

export interface RouteConstraint {
    maxDistance?: number;
    maxDuration?: number;
    maxCost?: number;
    timeWindows: boolean;
    priorityConstraint: boolean;
    vehicleType: VehicleType;
    maxLoad?: number;
}

export type VehicleType = 'car' | 'truck' | 'suv' | 'walking';

export type OptimizationGoal = 'shortest_distance' | 'shortest_time' | 'lowest_cost' | 'balanced';

export interface RoutePlanningRequest {
    samplingPoints: SamplingPoint[];
    startPoint: SamplingPoint;
    endPoint?: SamplingPoint;
    constraints: RouteConstraint;
    optimizationGoal: OptimizationGoal;
    algorithm: string;
    returnMultipleRoutes: boolean;
}

export interface RoutePlanningResponse {
    success: boolean;
    routes: PlannedRoute[];
    bestRoute?: PlannedRoute;
    statistics: Record<string, any>;
    warnings: string[];
    computationTime: number;
}

export interface RouteTemplate {
    templateId: string;
    name: string;
    description?: string;
    samplingPoints: SamplingPoint[];
    constraints: RouteConstraint;
    optimizationGoal: OptimizationGoal;
    createdAt: string;
    updatedAt: string;
}

export interface AlgorithmInfo {
    id: string;
    name: string;
    description: string;
}

export interface VehicleTypeInfo {
    id: string;
    name: string;
    description: string;
}

export interface OptimizationGoalInfo {
    id: string;
    name: string;
    description: string;
}

export interface ValidationResult {
    isValid: boolean;
    details: {
        is_valid: boolean;
        violations: string[];
        constraint_results: Record<string, any>;
    };
}