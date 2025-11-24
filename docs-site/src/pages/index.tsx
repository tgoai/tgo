import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import styles from './index.module.css';

// 引入 react-icons
import { 
  FaFacebookF, 
  FaFacebookMessenger, 
  FaInstagram, 
  FaWhatsapp, 
  FaTelegramPlane, 
  FaLine, 
  FaVk, 
  FaWeixin,
  FaTiktok
} from 'react-icons/fa';

import { SiZalo } from 'react-icons/si';

const IntegrationIcons = [
  { name: 'Facebook', color: '#1877F2', icon: <FaFacebookF /> },
  { name: 'Messenger', color: '#A834EA', icon: <FaFacebookMessenger /> },
  { name: 'Instagram', color: '#E4405F', icon: <FaInstagram /> },
  { name: 'WhatsApp', color: '#25D366', icon: <FaWhatsapp /> },
  { name: 'TikTok', color: '#000000', icon: <FaTiktok /> },
  { name: 'Telegram', color: '#0088CC', icon: <FaTelegramPlane /> },
  { name: 'Line', color: '#00C300', icon: <FaLine /> },
  { name: 'VK', color: '#0077FF', icon: <FaVk /> },
  { name: 'WeChat', color: '#07C160', icon: <FaWeixin /> },
  { name: 'Zalo', color: '#0068FF', icon: <SiZalo /> },
];

const ORBIT_RADIUS = 160;

// 打字机动画词汇
const TYPING_WORDS = ['意图', '情绪', '需求', '满意度'];

function Typewriter() {
  const [index, setIndex] = React.useState(0);
  const [subIndex, setSubIndex] = React.useState(0);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [blink, setBlink] = React.useState(true);

  // 光标闪烁
  React.useEffect(() => {
    const timeout2 = setTimeout(() => {
      setBlink((prev) => !prev);
    }, 500);
    return () => clearTimeout(timeout2);
  }, [blink]);

  React.useEffect(() => {
    if (index >= TYPING_WORDS.length) {
      setIndex(0); // 循环播放
      return;
    }

    const subText = TYPING_WORDS[index].substring(0, subIndex);

    if (isDeleting) {
      // 删除阶段
      if (subIndex === 0) {
        setIsDeleting(false);
        setIndex((prev) => prev + 1);
        return;
      }

      const timeout = setTimeout(() => {
        setSubIndex((prev) => prev - 1);
      }, 100); // 删除速度
      return () => clearTimeout(timeout);
    } else {
      // 输入阶段
      if (subIndex === TYPING_WORDS[index].length) {
        const timeout = setTimeout(() => {
          setIsDeleting(true);
        }, 2000); // 停留 2秒
        return () => clearTimeout(timeout);
      }

      const timeout = setTimeout(() => {
        setSubIndex((prev) => prev + 1);
      }, 150); // 输入速度
      return () => clearTimeout(timeout);
    }
  }, [subIndex, index, isDeleting]);

  return (
    <span className={styles.typewriterWrapper}>
      {TYPING_WORDS[index % TYPING_WORDS.length].substring(0, subIndex)}
      <span className={`${styles.cursor} ${blink ? styles.cursorBlink : ''}`}>|</span>
    </span>
  );
}

function OrbitIntegrations() {
  return (
    <div className={styles.orbitContainer}>
      {/* 背景连线层 (保留背景圆环，移除虚线连接) */}
      <svg className={styles.orbitLines} width="100%" height="100%" viewBox="-250 -250 500 500">
        <circle cx="0" cy="0" r={ORBIT_RADIUS} className={styles.orbitCircle} />
        {/* 已移除 <line> 虚线元素 */}
      </svg>

      {/* 中心 Tgo Logo */}
      <div className={styles.centerLogo}>
        <img src="img/logo.svg" alt="Tgo Logo" className={styles.logoImg} />
        {/* 呼吸光晕 */}
        <div className={styles.pulseRing}></div>
        <div className={styles.pulseRing} style={{animationDelay: '1s'}}></div>
      </div>

      {/* 卫星图标 */}
      {IntegrationIcons.map((item, idx) => {
        const total = IntegrationIcons.length;
        const angle = (idx * 360) / total - 90;
        
        return (
          <div 
            key={idx}
            className={styles.satelliteWrapper}
            style={{
              '--angle': `${angle}deg`,
              '--radius': `${ORBIT_RADIUS}px`,
              '--icon-color': item.color,
              '--delay': `${idx * 0.2}s`
            } as React.CSSProperties}
          >
            <div className={styles.satelliteIcon} title={item.name}>
              {item.icon}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={styles.heroBanner}>
      {/* 背景光晕 */}
      <div className={styles.bgGlow}></div>
      
      <div className="container">
        <div className={styles.heroContent}>
          <h1 className={styles.heroTitle}>
            <span className={styles.heroTitleHighlight}>客服智能体</span><br />
            更懂客户的<Typewriter />
          </h1>
          <p className={styles.heroSubtitle}>
            多渠道接入，知识库，多智能体协调，主流大模型支持
          </p>
          
          {/* 新的环绕式集成展示 (移除了 IntegrationsLabel) */}
          <div className={styles.integrationsSection}>
            <OrbitIntegrations />
          </div>

          <div className={styles.buttons}>
            <Link
              className="button button--primary button--lg"
              to="/quick-start">
              开启免费试用
            </Link>
            <Link
              className="button button--secondary button--lg"
              to="https://github.com/tgoai/tgo">
              预约演示
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): JSX.Element {
  return (
    <Layout
      title="首页"
      description="全渠道私域沟通工具文档">
      <main>
        <HomepageHeader />
      </main>
    </Layout>
  );
}
