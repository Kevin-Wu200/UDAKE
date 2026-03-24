import { APIService } from '../../services/API封装.js';
import { ConfigurableApiPanel } from './ConfigurableApiPanel.js';
import { panelConfigs } from './panelConfigs.js';

export class DataQualityPanel extends ConfigurableApiPanel {
    constructor(apiService: APIService) {
        super(apiService, panelConfigs.dataQuality);
    }
}
