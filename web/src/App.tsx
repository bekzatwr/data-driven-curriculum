import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Layout } from './components/Layout';
import { EmptyState, ToastProvider } from './components/ui';
import { AppStateProvider } from './state/app';
import { DatasetScope } from './state/dataset';
import { UploadPage } from './pages/UploadPage';
import { OverviewPage } from './pages/OverviewPage';
import { ComparisonPage } from './pages/ComparisonPage';
import { PlannerPage } from './pages/PlannerPage';
import { ReportPage } from './pages/ReportPage';
import { ReportsPage } from './pages/ReportsPage';

export function App() {
  return (
    <BrowserRouter>
      <AppStateProvider>
        <ToastProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<UploadPage />} />
              <Route path="datasets/:datasetId" element={<DatasetScope />}>
                <Route index element={<Navigate to="overview" replace />} />
                <Route path="overview" element={<OverviewPage />} />
                <Route path="comparison" element={<ComparisonPage />} />
                <Route path="plan" element={<PlannerPage />} />
              </Route>
              <Route path="reports" element={<ReportsPage />} />
              <Route path="plans/:planId" element={<ReportPage />} />
              <Route
                path="*"
                element={
                  <div className="card">
                    <EmptyState
                      icon={<Compass size={26} />}
                      title="Страница не найдена"
                      action={
                        <Link className="btn btn-primary" to="/">
                          На главную
                        </Link>
                      }
                    >
                      Проверьте адрес или начните с выбора набора данных.
                    </EmptyState>
                  </div>
                }
              />
            </Route>
          </Routes>
        </ToastProvider>
      </AppStateProvider>
    </BrowserRouter>
  );
}
