import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import { useColorMode } from '@docusaurus/theme-common';
import Translate, { translate } from '@docusaurus/Translate';
import styles from './index.module.css';

// 引入 react-icons
import { 
  FaWhatsapp,
  FaTelegramPlane,
  FaDiscord,
  FaSlack,
  FaFacebook,
  FaInstagram,
  FaTwitter,
  FaLinkedin,
  FaPhone
} from 'react-icons/fa';

import { 
  IoLogoWechat
} from 'react-icons/io5';

import {
  AiOutlineWechatWork
} from 'react-icons/ai';

import {
  TbWorld,
  TbUsers,
  TbMessageCircle
} from 'react-icons/tb';

import {
  MdEmail,
  MdSms
} from 'react-icons/md';

import {
  SiTiktok
} from 'react-icons/si';

import {
  FiShare2
} from 'react-icons/fi';

const IntegrationIcons = [
  { name: 'WeChat', color: '#07C160', icon: <IoLogoWechat /> },
  { name: 'WeCom', color: '#1AAD19', icon: <AiOutlineWechatWork /> },
  { name: 'WhatsApp', color: '#25D366', icon: <FaWhatsapp /> },
  { name: 'Telegram', color: '#0088CC', icon: <FaTelegramPlane /> },
  { name: 'TikTok', color: '#000000', icon: <SiTiktok /> },
  { name: 'Facebook', color: '#1877F2', icon: <FaFacebook /> },
  { name: 'Instagram', color: '#E4405F', icon: <FaInstagram /> },
  { name: 'Twitter', color: '#1DA1F2', icon: <FaTwitter /> },
  { name: 'Discord', color: '#5865F2', icon: <FaDiscord /> },
  { name: 'Slack', color: '#4A154B', icon: <FaSlack /> },
  { name: 'LinkedIn', color: '#0A66C2', icon: <FaLinkedin /> },
  { name: 'Email', color: '#EA4335', icon: <MdEmail /> },
  { name: 'SMS', color: '#34A853', icon: <MdSms /> },
  { name: 'Website', color: '#6366F1', icon: <TbWorld /> },
];

const ORBIT_RADIUS = 160;

// 打字机动画词汇 - 多语言
const TYPING_WORDS_ZH = ['意图', '情绪', '需求', '满意度'];
const TYPING_WORDS_EN = ['Intent', 'Emotion', 'Needs', 'Satisfaction'];

function Typewriter() {
  const { i18n } = useDocusaurusContext();
  const isEnglish = i18n.currentLocale === 'en';
  const TYPING_WORDS = isEnglish ? TYPING_WORDS_EN : TYPING_WORDS_ZH;
  
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
  }, [subIndex, index, isDeleting, TYPING_WORDS]);

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
  const { siteConfig, i18n } = useDocusaurusContext();
  const { colorMode } = useColorMode();
  const isEnglish = i18n.currentLocale === 'en';
  
  const productImage = useBaseUrl(
    colorMode === 'dark' 
      ? (isEnglish ? '/img/screen/en/home_dark.png' : '/img/screen/home_dark.png')
      : (isEnglish ? '/img/screen/en/home.png' : '/img/screen/home.png')
  );

  return (
    <header className={styles.heroBanner} style={{marginTop: "-64px"}}>
      {/* 背景光晕 */}
      <div className={styles.bgGlow}></div>
      
      <div className="container" style={{marginTop: "84px"}}>
        <div className={styles.heroContent}>
          <h1 className={styles.heroTitle}>
            <span className={styles.heroTitleHighlight}>
              <Translate id="homepage.hero.title.highlight">客服智能体</Translate>
            </span><br />
            <Translate id="homepage.hero.title.prefix">更懂客户的</Translate><Typewriter />
          </h1>
          <p className={styles.heroSubtitle}>
            <Translate id="homepage.hero.subtitle">
              多渠道接入，知识库，多智能体协调，主流大模型支持
            </Translate>
          </p>
          
          {/* 新的环绕式集成展示 (移除了 IntegrationsLabel) */}
          <div className={styles.integrationsSection}>
            <OrbitIntegrations />
          </div>

          <div className={styles.buttons}>
            <Link
              className="button button--primary button--lg"
              to="/quick-start/deploy">
              <Translate id="homepage.hero.button.getStarted">快速开始</Translate>
            </Link>
            <Link
              className="button button--secondary button--lg"
              to="https://github.com/tgoai/tgo">
              GitHub
            </Link>
          </div>

          {/* 产品截图 */}
          <div className={styles.productImageSection}>
            <img 
              src={productImage} 
              alt={translate({
                id: 'homepage.hero.productImage.alt',
                message: 'Tgo 产品截图',
              })}
              className={styles.productImage}
            />
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): JSX.Element {
  return (
    <Layout
      title={translate({
        id: 'homepage.title',
        message: '首页',
      })}
      description={translate({
        id: 'homepage.description',
        message: '开源 AI 智能体客服平台',
      })}>
      <main>
        <HomepageHeader />
      </main>
    </Layout>
  );
}
