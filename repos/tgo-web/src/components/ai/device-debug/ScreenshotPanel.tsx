/**
 * Screenshot Panel
 * Displays the latest screenshot and screenshot gallery
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Image as ImageIcon,
  Maximize2,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';

export default function ScreenshotPanel() {
  const { t } = useTranslation();
  const { screenshots, latestScreenshot } = useDeviceDebugStore();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const handleOpenFullscreen = (index?: number) => {
    setSelectedIndex(index ?? screenshots.length - 1);
    setIsFullscreen(true);
  };

  const handleCloseFullscreen = () => {
    setIsFullscreen(false);
    setSelectedIndex(null);
  };

  const handlePrevious = () => {
    if (selectedIndex !== null && selectedIndex > 0) {
      setSelectedIndex(selectedIndex - 1);
    }
  };

  const handleNext = () => {
    if (selectedIndex !== null && selectedIndex < screenshots.length - 1) {
      setSelectedIndex(selectedIndex + 1);
    }
  };

  const currentScreenshot =
    selectedIndex !== null ? screenshots[selectedIndex] : null;

  return (
    <div className="space-y-8">
      {latestScreenshot ? (
        <div className="space-y-6">
          {/* Latest Screenshot Preview */}
          <div
            className="group relative cursor-pointer overflow-hidden rounded-[2.5rem] border border-white/10 bg-black shadow-[0_30px_60px_rgba(0,0,0,0.5)]"
            onClick={() => handleOpenFullscreen()}
          >
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-all duration-700 z-10" />
            <img
              src={`data:image/png;base64,${latestScreenshot.data}`}
              alt="Latest screenshot"
              className="aspect-video w-full object-contain transition-transform duration-1000 group-hover:scale-105"
            />
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-500 z-20">
              <div className="p-5 bg-white/10 backdrop-blur-xl rounded-full border border-white/20 shadow-2xl scale-90 group-hover:scale-100 transition-transform duration-500">
                <Maximize2 className="h-8 w-8 text-white" />
              </div>
            </div>
            
            {/* Overlay Info */}
            <div className="absolute bottom-5 left-5 right-5 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-all duration-500 z-20 translate-y-2 group-hover:translate-y-0">
              <span className="text-[10px] font-black text-white/70 bg-white/5 backdrop-blur-md px-3 py-1.5 rounded-xl border border-white/10 uppercase tracking-widest">
                {new Date(latestScreenshot.timestamp).toLocaleTimeString()}
              </span>
              {latestScreenshot.toolName && (
                <span className="text-[10px] font-black text-blue-400 bg-blue-500/10 backdrop-blur-md px-3 py-1.5 rounded-xl border border-blue-500/20 uppercase tracking-widest">
                  {latestScreenshot.toolName}
                </span>
              )}
            </div>
          </div>

          {/* Screenshot Gallery */}
          {screenshots.length > 1 && (
            <div className="pt-2">
              <div className="flex items-center justify-between mb-4 px-1">
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">
                  {t('deviceDebug.allScreenshots', 'Visual History')}
                </p>
                <span className="text-[10px] font-bold text-slate-600 bg-white/5 px-2 py-0.5 rounded-md border border-white/5">{screenshots.length}</span>
              </div>
              <div className="flex gap-4 overflow-x-auto pb-6 custom-scrollbar snap-x">
                {screenshots.map((screenshot, index) => (
                  <button
                    key={screenshot.id}
                    onClick={() => handleOpenFullscreen(index)}
                    className={`shrink-0 relative group rounded-2xl border-2 transition-all duration-500 overflow-hidden snap-center ${
                      screenshot.id === latestScreenshot.id
                        ? 'border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.3)] scale-105'
                        : 'border-white/5 hover:border-white/20'
                    }`}
                  >
                    <img
                      src={`data:image/png;base64,${screenshot.data}`}
                      alt={`Screenshot ${index + 1}`}
                      className="h-20 w-32 object-cover transition-transform duration-700 group-hover:scale-110"
                    />
                    <div className="absolute inset-0 bg-blue-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                    {screenshot.id === latestScreenshot.id && (
                      <div className="absolute top-2 right-2 w-2 h-2 bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex aspect-video flex-col items-center justify-center rounded-[3rem] border-2 border-dashed border-white/5 bg-white/5 group hover:border-white/10 transition-all duration-700">
          <div className="p-6 bg-slate-900 rounded-[2rem] group-hover:scale-110 transition-transform duration-500 border border-white/5 shadow-2xl">
            <ImageIcon className="h-10 w-10 text-slate-700" />
          </div>
          <p className="mt-6 text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">
            {t('deviceDebug.noScreenshot', 'Waiting for Visual Data')}
          </p>
        </div>
      )}

      {/* Fullscreen Modal */}
      {isFullscreen && currentScreenshot && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/98 backdrop-blur-2xl animate-in fade-in duration-500">
          {/* Close button */}
          <button
            onClick={handleCloseFullscreen}
            className="absolute right-10 top-10 rounded-[1.5rem] bg-white/5 p-4 text-white/50 transition-all hover:bg-white/10 hover:text-white border border-white/10 shadow-2xl active:scale-95"
          >
            <X className="h-8 w-8" />
          </button>

          {/* Navigation */}
          {screenshots.length > 1 && (
            <>
              <button
                onClick={handlePrevious}
                disabled={selectedIndex === 0}
                className="absolute left-10 rounded-[2rem] bg-white/5 p-6 text-white/30 transition-all hover:bg-white/10 hover:text-white disabled:opacity-5 border border-white/10 group shadow-2xl active:scale-95"
              >
                <ChevronLeft className="h-10 w-10 group-hover:-translate-x-1 transition-transform" />
              </button>
              <button
                onClick={handleNext}
                disabled={selectedIndex === screenshots.length - 1}
                className="absolute right-10 rounded-[2rem] bg-white/5 p-6 text-white/30 transition-all hover:bg-white/10 hover:text-white disabled:opacity-5 border border-white/10 group shadow-2xl active:scale-95"
              >
                <ChevronRight className="h-10 w-10 group-hover:translate-x-1 transition-transform" />
              </button>
            </>
          )}

          {/* Image Container */}
          <div className="relative max-h-[80vh] max-w-[85vw] group">
            <div className="absolute -inset-10 bg-blue-600/10 blur-[100px] rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-1000" />
            <img
              src={`data:image/png;base64,${currentScreenshot.data}`}
              alt="Screenshot fullscreen"
              className="relative rounded-3xl shadow-[0_50px_100px_rgba(0,0,0,0.8)] border border-white/10 object-contain max-h-[80vh] max-w-[85vw]"
            />
          </div>

          {/* Info Footer */}
          <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-6 px-8 py-4 rounded-[2rem] bg-white/5 backdrop-blur-2xl border border-white/10 shadow-2xl">
            <span className="text-xs font-mono font-black text-white/30 tracking-tighter">
              {selectedIndex !== null && `${selectedIndex + 1} / ${screenshots.length}`}
            </span>
            <div className="w-px h-4 bg-white/10" />
            <span className="text-xs font-black text-white/80 uppercase tracking-[0.2em]">
              {new Date(currentScreenshot.timestamp).toLocaleTimeString()}
            </span>
            {currentScreenshot.toolName && (
              <>
                <div className="w-px h-4 bg-white/10" />
                <span className="text-xs font-black text-blue-400 uppercase tracking-[0.2em]">
                  {currentScreenshot.toolName}
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
