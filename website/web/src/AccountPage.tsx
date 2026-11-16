import {t,useLanguage} from './i18n';
import Icon from './Icon';
import {chooseLanguage,dismissSyncError,useAccount} from './account';
import {ThemeChoices,useThemeSnapshot} from './ThemeControl';

/** Account information, password, synced theme and language, and sign-out. Nothing else is configured here. */
export default function AccountPage({onPassword,onLogout}:{onPassword:()=>void;onLogout:()=>void}){
 const language=useLanguage(),{user,syncError}=useAccount(),snapshot=useThemeSnapshot();
 if(!user)return null;
 return <main id="main" className="workspace personal-page account-page">
  <header className="personal-heading"><span className="eyebrow">{t('ACCOUNT')}</span><h1 tabIndex={-1}>{t('账户设置')}</h1></header>
  <div className="account-sections">
   <section className="panel account-section" aria-labelledby="account-profile"><h2 id="account-profile">{t('账户')}</h2>
    <dl className="account-facts"><div><dt>{t('用户名')}</dt><dd>{user.username}</dd></div><div><dt>{t('角色')}</dt><dd>{user.role==='admin'?t('管理员'):t('读者')}</dd></div></dl>
    <div className="account-actions"><button type="button" onClick={onPassword}><Icon name="key"/>{t('修改密码')}</button><button type="button" onClick={onLogout}><Icon name="logout"/>{t('退出登录')}</button></div>
    <p className="hint">{t('忘记密码时请联系管理员重置。')}</p>
   </section>
   <section className="panel account-section" aria-labelledby="account-preferences"><h2 id="account-preferences">{t('外观与语言')}</h2>
    <p className="muted">{t('自动同步到你登录的其他设备。')}</p>
    {syncError&&<p className="error account-sync-error" role="alert">{t(syncError)}<button type="button" className="text-button" onClick={dismissSyncError}>{t('关闭')}</button></p>}
    <h3>{t('界面语言')}</h3>
    <div className="language-switch account-language" role="group" aria-label={t('界面语言')}><button type="button" lang="zh-CN" aria-pressed={language==='zh'} onClick={()=>chooseLanguage('zh')}>{t('中文')}</button><button type="button" lang="en" aria-pressed={language==='en'} onClick={()=>chooseLanguage('en')}>{t('English')}</button></div>
    <h3>{t('主题')}</h3>
    <ThemeChoices snapshot={snapshot}/>
   </section>
  </div>
 </main>;
}
