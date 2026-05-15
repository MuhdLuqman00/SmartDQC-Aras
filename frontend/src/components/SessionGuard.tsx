import React from 'react';
import { FolderOpen } from 'lucide-react';
import { EmptyState } from './EmptyState';
import { useSession } from '../context/SessionContext';
import { useLang } from '../context/LanguageContext';

export function SessionGuard({ children }: { children: React.ReactNode }) {
  const { cacheId } = useSession();
  const { t } = useLang();

  if (!cacheId) {
    return (
      <EmptyState
        icon={<FolderOpen size={48} />}
        title={t('No active session', 'Tiada sesi aktif')}
        description={t(
          'Upload a dataset to begin analysis.',
          'Muat naik dataset untuk memulakan analisis.',
        )}
        action={{ label: t('Upload Dataset', 'Muat Naik Dataset'), to: '/upload' }}
      />
    );
  }

  return <>{children}</>;
}
