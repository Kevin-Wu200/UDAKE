import { initializeMap } from './地图初始化.js';
import { LayerManager } from './图层管理.js';
import { TaskPoller } from './任务轮询.js';
import { APIService } from './services/API封装.js';
import { CoordinateSystemInfo } from './坐标系统信息.js';
import { SinglePointSampling } from './单点采样输入.js';
import { GeoJSONParser } from './utils/geojsonParser.js';
import { DataImportModal } from './components/DataImportModal.js';
import { NewProjectModal } from './components/NewProjectModal.js';
import { FreeSampling } from './sampling/FreeSampling.js';
import { RegionSampling } from './sampling/RegionSampling.js';
import { Project } from './models/Project.js';
import { LocationPermissionManager } from './utils/locationPermissionManager.js';
import { SamplingRecommendationPanel } from './components/SamplingRecommendationPanel.js';

console.log("主程序已执行");

class App {
    constructor() {
        console.log("App 构造函数执行");
        this.apiService = null;
        this.layerManager = null;
        this.taskPoller = null;
        this.currentDataId = null;
        this.currentTaskId = null;
        this.view = null;
        this.currentProject = null;
        this.samplingComponent = null;
        this.recommendationPanel = null;

        this.init();
    }

    /*
    async init() {
        console.log("init 被执行");
        // 获取后端端口（Electron 环境）或使用默认端口
        let backendPort = 8000;
        if (window.electronAPI) {
            try {
                backendPort = await window.electronAPI.getBackendPort();
                console.log('Electron 环境，后端端口:', backendPort);
            } catch (error) {
                console.warn('获取后端端口失败，使用默认端口 8000');
            }
        }

        // 初始化 API 服务
        this.apiService = new APIService(`http://localhost:${backendPort}/api`);

        // 初始化地图
        this.view = await initializeMap('viewDiv');
        this.layerManager = new LayerManager(this.view);

        // 初始化新组件
        this.initializeComponents(this.view);

        // 绑定事件
        this.bindEvents;

        console.log('应用初始化完成');
    }
    */

    async init() {
    console.log("init 被执行");

    let backendPort = 8000;

    if (window.electronAPI) {
        try {
            backendPort = await window.electronAPI.getBackendPort();
            console.log("获取端口完成");
        } catch (error) {
            console.warn("获取端口失败");
        }
    }

    console.log("准备初始化 API");
    this.apiService = new APIService(`http://localhost:${backendPort}/api`);
    console.log("API 初始化完成");

    console.log("准备初始化地图");
    const mapAdapter = await initializeMap('viewDiv');
    this.view = mapAdapter.getView();
    this.layerManager = new LayerManager(mapAdapter);
    console.log("地图初始化完成");

    console.log("准备初始化组件");
    this.initializeComponents(this.view);
    console.log("组件初始化完成");

    // 初始化定位权限（不阻塞后续流程）
    console.log("准备检测定位权限");
    LocationPermissionManager.requestPermission().then(status => {
        console.log("定位权限状态:", status);
    });

    console.log("准备绑定事件");
    this.bindEvents();
    console.log("bindEvents 调用完成");

    console.log("应用初始化完成");
    }

    /**
     * 初始化新组件
     */
    initializeComponents(view) {
        const sidebar = document.querySelector('.sidebar');

        // 创建坐标系统信息组件
        const coordSystemInfo = new CoordinateSystemInfo(view);
        const coordPanel = coordSystemInfo.createPanel();

        // 创建单点采样输入组件
        const singlePointSampling = new SinglePointSampling(view, (pointData) => {
            this.layerManager.addSamplingPoint(pointData);
        });
        const samplingPanel = singlePointSampling.createPanel();

        // 创建采样建议面板
        this.recommendationPanel = new SamplingRecommendationPanel(
            view,
            this.layerManager,
            (recommendation) => this.handleRecommendationSelect(recommendation)
        );
        const recommendationPanel = this.recommendationPanel.createPanel();

        // 插入到侧边栏
        const firstPanel = sidebar.querySelector('.panel');
        sidebar.insertBefore(coordPanel, firstPanel);

        const interpolationPanel = sidebar.querySelectorAll('.panel')[2];
        interpolationPanel.parentNode.insertBefore(samplingPanel, interpolationPanel.nextSibling);

        // 将采样建议面板添加到右侧侧边栏
        const rightSidebarContent = document.querySelector('.right-sidebar-content');
        if (rightSidebarContent) {
            rightSidebarContent.appendChild(recommendationPanel);
        }

        // 绑定侧边栏切换按钮
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => this.toggleRightSidebar());
        }
    }

    bindEvents() {
        console.log("bindEvents 执行");

        // 新建项目按钮
        document.getElementById('new-project-btn').addEventListener('click', () => this.handleNewProject());

        // 文件选择器交互
        const picker = document.getElementById("file-picker");
        const fileInput = document.getElementById("file-input");
        const fileName = document.getElementById("file-name");

        console.log("picker:", picker);
        console.log("fileInput:", fileInput);

        picker.addEventListener("click", () => {
            console.log("file-picker 被点击");
            try {
                fileInput.click();
                console.log("fileInput.click() 已执行");
            } catch (e) {
                console.error("click 被阻止:", e);
            }
        });

        fileInput.addEventListener("change", () => {
            if (fileInput.files.length > 0) {
                fileName.textContent = fileInput.files[0].name;
            } else {
                fileName.textContent = "点击选择 GeoJSON 文件";
            }
        });

        // 文件上传
        document.getElementById('upload-btn').addEventListener('click', () => this.handleUpload());

        // 网格分辨率实时校验
        const gridResolutionInput = document.getElementById('grid-resolution');
        gridResolutionInput.addEventListener('input', () => this.validateGridResolution());

        // 开始插值
        document.getElementById('start-kriging-btn').addEventListener('click', () => this.handleStartKriging());

        // 图层控制
        document.getElementById('layer-points').addEventListener('change', (e) => {
            this.layerManager.toggleLayer('points', e.target.checked);
        });
        document.getElementById('layer-prediction').addEventListener('change', (e) => {
            this.layerManager.toggleLayer('prediction', e.target.checked);
        });
        document.getElementById('layer-variance').addEventListener('change', (e) => {
            this.layerManager.toggleLayer('variance', e.target.checked);
        });

        // 导出按钮
        document.getElementById('export-prediction-geojson').addEventListener('click', () => {
            this.handleExport('prediction', 'geojson');
        });
        document.getElementById('export-prediction-shp').addEventListener('click', () => {
            this.handleExport('prediction', 'shp');
        });
        document.getElementById('export-prediction-tif').addEventListener('click', () => {
            this.handleExport('prediction', 'tif');
        });
        document.getElementById('export-variance-geojson').addEventListener('click', () => {
            this.handleExport('variance', 'geojson');
        });
        document.getElementById('export-variance-shp').addEventListener('click', () => {
            this.handleExport('variance', 'shp');
        });
        document.getElementById('export-variance-tif').addEventListener('click', () => {
            this.handleExport('variance', 'tif');
        });
    }

    /**
     * 处理新建项目
     */
    handleNewProject() {
        const modal = new NewProjectModal(
            (project, config) => this.onProjectCreated(project, config),
            this.view
        );
        modal.show();
    }

    /**
     * 项目创建完成回调
     */
    onProjectCreated(project, config) {
        console.log('项目创建完成:', project);

        // 保存当前项目
        this.currentProject = project;

        // 清理旧的采样组件
        if (this.samplingComponent) {
            this.samplingComponent.destroy();
        }

        // 创建采样组件
        const projectPanel = document.getElementById('project-panel');
        const projectContent = document.getElementById('project-content');

        // 清空内容
        projectContent.innerHTML = '';

        // 根据采样模式创建对应组件
        if (config.sampling_mode === 'free') {
            this.samplingComponent = new FreeSampling(
                this.view,
                (pointData) => this.handlePointAdded(pointData)
            );
            const panel = this.samplingComponent.createPanel(config.coordinate_mode);
            projectContent.appendChild(panel);

        } else if (config.sampling_mode === 'region') {
            this.samplingComponent = new RegionSampling(
                this.view,
                (pointData) => this.handlePointAdded(pointData)
            );
            const panel = this.samplingComponent.createPanel(config.coordinate_mode);
            projectContent.appendChild(panel);
        }

        // 显示项目面板
        projectPanel.style.display = 'block';
    }

    /**
     * 处理采样点添加
     */
    async handlePointAdded(pointData) {
        console.log('添加采样点:', pointData);

        // 添加到项目
        const success = this.currentProject.addPoint(pointData);

        if (!success) {
            throw new Error('采样点超出区域边界');
        }

        // 在地图上显示
        await this.layerManager.addSamplingPoint(pointData);

        // 校验网格分辨率后再决定是否启用按钮
        this.validateGridResolution();
    }

    /**
     * 校验网格分辨率输入
     * 规则：
     * 1. 不能为空
     * 2. 只能为整数
     * 3. 必须大于 0
     * 4. 禁止小数、负数、科学计数法、字母、空格
     * 5. 禁止前导 + 或 -
     * 6. 限制最大值为 10000
     */
    validateGridResolution() {
        const input = document.getElementById('grid-resolution');
        const errorMsg = document.getElementById('grid-resolution-error');
        const startBtn = document.getElementById('start-kriging-btn');
        const value = input.value.trim();

        // 合法格式：只允许1-9开头的正整数
        const validPattern = /^[1-9]\d*$/;

        // 检查是否为空
        if (value === '') {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        // 检查格式是否合法
        if (!validPattern.test(value)) {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        // 检查数值范围
        const numValue = parseInt(value, 10);
        if (numValue > 10000) {
            input.classList.add('error');
            errorMsg.classList.add('show');
            startBtn.disabled = true;
            return false;
        }

        // 合法输入，移除错误状态
        input.classList.remove('error');
        errorMsg.classList.remove('show');

        // 根据是否有足够的采样点来决定是否启用按钮
        const hasEnoughPoints = (this.currentProject && this.currentProject.getPointCount() >= 3) ||
                                (this.layerManager && this.layerManager.getSamplingPoints().length >= 3);
        startBtn.disabled = !hasEnoughPoints;

        return true;
    }

    async handleUpload() {
        const fileInput = document.getElementById('file-input');
        const file = fileInput.files[0];

        if (!file) {
            this.showStatus('请选择文件', 'error');
            return;
        }

        // 验证文件类型
        if (!GeoJSONParser.validateFileType(file)) {
            this.showStatus('仅支持 .geojson 或 .json 文件', 'error');
            return;
        }

        try {
            console.log('开始解析 GeoJSON 文件');

            // 解析 GeoJSON
            const parseResult = await GeoJSONParser.parseFile(file);
            console.log('GeoJSON 解析成功:', parseResult);

            // 显示配置弹窗
            console.log('准备显示弹窗');
            const modal = new DataImportModal((transformedData) => {
                this.handleDataImport(transformedData);
            }, this.view);

            modal.show(parseResult);
            console.log('弹窗显示完成');

        } catch (error) {
            console.error('上传失败:', error);
            this.showStatus(error.message, 'error');
        }
    }

    /**
     * 处理数据导入
     */
    async handleDataImport(transformedData) {
        try {
            // 在地图上绘制采样点
            await this.layerManager.addPointsLayer(transformedData.geojson);

            // 将数据添加到采样点数组
            transformedData.data.forEach(point => {
                this.layerManager.samplingPoints.push(point);
            });

            this.showStatus(`数据导入成功！点数: ${transformedData.data.length}`, 'success');

            // 校验网格分辨率后再决定是否启用按钮
            this.validateGridResolution();

        } catch (error) {
            this.showStatus(`导入失败: ${error.message}`, 'error');
        }
    }

    async handleStartKriging() {
        // 再次校验网格分辨率
        if (!this.validateGridResolution()) {
            this.showStatus('网格分辨率输入不合法', 'error');
            return;
        }

        // 优先使用当前项目的采样点
        let samplingPoints;

        if (this.currentProject && this.currentProject.getPointCount() > 0) {
            samplingPoints = this.currentProject.points;
        } else {
            samplingPoints = this.layerManager.getSamplingPoints();
        }

        if (!samplingPoints || samplingPoints.length === 0) {
            this.showStatus('请先上传数据或添加采样点', 'error');
            return;
        }

        if (samplingPoints.length < 3) {
            this.showStatus('至少需要 3 个采样点才能进行插值', 'error');
            return;
        }

        const params = {
            points: samplingPoints,
            method: document.getElementById('kriging-method').value,
            variogram_model: document.getElementById('variogram-model').value,
            grid_resolution: parseInt(document.getElementById('grid-resolution').value, 10),
            enable_cross_validation: true
        };

        try {
            const response = await this.apiService.startKriging(params);
            this.currentTaskId = response.task_id;

            this.showStatus('任务已启动', 'success');
            this.startTaskPolling();

        } catch (error) {
            this.showStatus(`启动失败: ${error.message}`, 'error');
        }
    }

    startTaskPolling() {
        if (this.taskPoller) {
            this.taskPoller.stop();
        }

        this.taskPoller = new TaskPoller(
            this.apiService,
            this.currentTaskId,
            (status) => this.handleTaskUpdate(status)
        );

        this.taskPoller.start();
    }

    async handleTaskUpdate(status) {
        const statusDiv = document.getElementById('task-status');
        const progressBar = document.getElementById('progress-bar');
        const progressFill = progressBar.querySelector('.progress-fill');

        statusDiv.innerHTML = `
            <p>状态: ${status.status}</p>
            <p>进度: ${status.progress.toFixed(1)}%</p>
        `;

        progressBar.style.display = 'block';
        progressFill.style.width = `${status.progress}%`;

        if (status.status === 'completed') {
            this.taskPoller.stop();
            this.showStatus('插值完成！', 'success');
            await this.loadResults();
        } else if (status.status === 'failed') {
            this.taskPoller.stop();
            this.showStatus(`任务失败: ${status.error}`, 'error');
        }
    }

    async loadResults() {
        try {
            const predictionResult = await this.apiService.getPredictionResult(this.currentTaskId);
            const varianceResult = await this.apiService.getVarianceResult(this.currentTaskId);

            // 加载栅格图层
            this.layerManager.addRasterLayer('prediction', predictionResult.geotiff_url);
            this.layerManager.addRasterLayer('variance', varianceResult.geotiff_url);

            // 显示导出面板
            document.getElementById('export-panel').style.display = 'block';

            // 设置采样建议面板的任务ID，自动生成建议
            if (this.recommendationPanel) {
                this.recommendationPanel.setTaskId(this.currentTaskId);
            }

        } catch (error) {
            console.error('加载结果失败:', error);
        }
    }

    /**
     * 处理导出
     */
    async handleExport(dataType, format) {
        if (!this.currentTaskId) {
            this.showExportStatus('没有可导出的结果', 'error');
            return;
        }

        const filename = `${this.currentTaskId}_${dataType}.${format}`;
        this.showExportStatus(`正在下载 ${filename}...`, 'success');

        try {
            await this.apiService.downloadExportFile(this.currentTaskId, filename);
            this.showExportStatus(`${filename} 下载完成`, 'success');
        } catch (error) {
            console.error('导出失败:', error);
            this.showExportStatus(`导出失败: ${error.message}`, 'error');
        }
    }

    showExportStatus(message, type) {
        const statusDiv = document.getElementById('export-status');
        statusDiv.textContent = message;
        statusDiv.className = `status-message ${type}`;
    }

    showStatus(message, type) {
        const statusDiv = document.getElementById('upload-status');
        statusDiv.textContent = message;
        statusDiv.className = `status-message ${type}`;
    }

    /**
     * 切换右侧侧边栏
     */
    toggleRightSidebar() {
        const rightSidebar = document.getElementById('right-sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');

        if (rightSidebar.classList.contains('hidden')) {
            rightSidebar.classList.remove('hidden');
            sidebarToggle.classList.remove('open');
        } else {
            rightSidebar.classList.add('hidden');
            sidebarToggle.classList.add('open');
        }
    }

    /**
     * 处理建议点选中
     * @param {Object} recommendation - 建议点数据
     */
    handleRecommendationSelect(recommendation) {
        console.log('选中建议点:', recommendation);

        // 如果有采样组件，自动填充坐标
        if (this.samplingComponent && this.samplingComponent.coordinateInput) {
            // 填充坐标
            this.samplingComponent.coordinateInput.setValue({
                longitude: recommendation.x,
                latitude: recommendation.y
            });

            // 显示提示信息
            this.showStatus(
                `已选择建议点 #${recommendation.id}，坐标已自动填充`,
                'success'
            );
        } else {
            this.showStatus(
                `建议点 #${recommendation.id} 坐标: ${recommendation.x.toFixed(6)}, ${recommendation.y.toFixed(6)}`,
                'success'
            );
        }
    }
}

// 启动应用
const app = new App();