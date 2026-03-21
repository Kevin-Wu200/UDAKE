export interface CSSFeatureSupport {
    backdropFilter: boolean;
    flexGap: boolean;
    scrollbarStyle: boolean;
}

function detectFlexGapSupport(): boolean {
    const flex = document.createElement('div');
    flex.style.display = 'flex';
    flex.style.flexDirection = 'column';
    flex.style.rowGap = '1px';

    const childA = document.createElement('div');
    const childB = document.createElement('div');
    childA.style.height = '1px';
    childB.style.height = '1px';
    flex.appendChild(childA);
    flex.appendChild(childB);

    document.body.appendChild(flex);
    const supportsGap = flex.scrollHeight === 3;
    flex.remove();
    return supportsGap;
}

export class CSSFeatureDetector {
    static detect(): CSSFeatureSupport {
        const backdropFilter = CSS.supports('backdrop-filter', 'blur(2px)') ||
            CSS.supports('-webkit-backdrop-filter', 'blur(2px)');
        const flexGap = detectFlexGapSupport();
        const scrollbarStyle = CSS.supports('scrollbar-color', 'auto auto');

        return {
            backdropFilter,
            flexGap,
            scrollbarStyle
        };
    }

    static applyFeatureClasses(features: CSSFeatureSupport): void {
        const html = document.documentElement;

        html.classList.toggle('supports-backdrop-filter', features.backdropFilter);
        html.classList.toggle('no-backdrop-filter', !features.backdropFilter);

        html.classList.toggle('supports-flex-gap', features.flexGap);
        html.classList.toggle('no-flex-gap', !features.flexGap);

        html.classList.toggle('supports-scrollbar-style', features.scrollbarStyle);
        html.classList.toggle('no-scrollbar-style', !features.scrollbarStyle);
    }

    static init(): CSSFeatureSupport {
        const features = this.detect();
        this.applyFeatureClasses(features);
        return features;
    }
}
