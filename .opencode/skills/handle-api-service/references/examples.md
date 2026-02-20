# API Service Examples

This file contains real-world examples from the codebase.

## Example 1: Authentication Service

### Service Definition

```typescript
// src/services/gin/auth.service.ts
import { ginApiService } from '.'
import type { IUser } from '../../types/common'

export default class AuthService {
    private static readonly BASE_URL = '/auth'

    static login = async (username: string, password: string) => {
        const res = await ginApiService(`${this.BASE_URL}/login`, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        })
        return res.data
    }

    static register = async (username: string, password: string) => {
        const res = await ginApiService(`${this.BASE_URL}/register`, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        })
        return res.data
    }

    static getProfile = async (): Promise<IUser> => {
        const res = await ginApiService<{ data: IUser }>(`${this.BASE_URL}/profile`)
        return res.data
    }
}
```

### Type Definition

```typescript
// src/types/common.ts
export interface IUser {
    name: string
    email: string
}
```

### Login Component (Mutation Example with i18n)

```typescript
// src/components/pages/login/index.tsx
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../../../stores/notification/notification.selector'
import AuthService from '../../../services/gin/auth.service'
import { tokenFacade } from '../../../stores/token/token.facade'
import { useNavigate } from '@tanstack/react-router'

const LoginPage: React.FC = () => {
    const { t } = useTranslation('auth') // IMPORTANT: Use useTranslation hook
    const notify = useNotify()
    const navigate = useNavigate()

    const mutationLogin = useMutation({
        mutationFn: (data: LoginFormData) => AuthService.login(data.username, data.password),
        onSuccess: (data) => {
            notify(t('login.success.loginSuccess'), 'success') // Use t() for translation
            tokenFacade.login(data.accessToken, data.refreshToken)
            setTimeout(() => {
                navigate({ to: '/' })
            }, 500)
        },
        onError: () => {
            notify(t('login.error.invalidCredentials'), 'error') // Use t() for translation
        }
    })

    const handleSubmit = (data: LoginFormData) => {
        mutationLogin.mutate(data)
    }

    return (
        <form onSubmit={form.handleSubmit(handleSubmit)}>
            {/* form fields */}
            <Button
                type="submit"
                loading={mutationLogin.isPending}
            >
                {t('login.submit')} {/* Also use t() for button text */}
            </Button>
        </form>
    )
}
```

**Corresponding i18n file:**

```json
// src/i18n/locales/en/auth.json
{
    "login": {
        "title": "Welcome Back",
        "subtitle": "Sign in to your account",
        "username": "Username",
        "password": "Password",
        "submit": "Sign in",
        "error": {
            "usernameRequired": "Username is required",
            "passwordRequired": "Password is required",
            "invalidCredentials": "Invalid username or password"
        },
        "success": {
            "loginSuccess": "Login successful"
        }
    }
}
```

### Profile Component (Query Example)

```typescript
// src/components/pages/personal/index.tsx
import { useQuery } from '@tanstack/react-query'
import { CircularProgress } from '@mui/material'
import AuthService from '../../../services/gin/auth.service'

const Personal: React.FC = () => {
    const queryUserProfile = useQuery({
        queryKey: ['userProfile'],
        queryFn: () => AuthService.getProfile(),
        retry: 1
    })

    if (queryUserProfile.isPending) {
        return <CircularProgress />
    }

    if (queryUserProfile.isError) {
        return <Typography color="error">Failed to load profile</Typography>
    }

    const user = queryUserProfile.data

    return (
        <div>
            <Typography>Name: {user?.name}</Typography>
            <Typography>Email: {user?.email}</Typography>
        </div>
    )
}
```

## Important: i18n Integration

**This project uses i18n (react-i18next).** All notification messages MUST use the `useTranslation` hook and `t()` function.

**Pattern:**

1. Import `useTranslation` from `react-i18next`
2. Call `const { t } = useTranslation('namespace')` at component start
3. Use `t('key.path')` for all notification messages
4. Ensure translation keys exist in `src/i18n/locales/en/[namespace].json`

## Example 2: Document Service (CRUD Operations)

### Service Definition

```typescript
// src/services/gin/document.service.ts
import { ginApiService } from '.'
import type { IDocument } from '../../types/common'

export default class DocumentService {
    private static readonly BASE_URL = '/documents'

    // GET - List all documents
    static getDocuments = async (): Promise<IDocument[]> => {
        const res = await ginApiService<{ data: IDocument[] }>(`${this.BASE_URL}`)
        return res.data
    }

    // GET - Single document
    static getDocument = async (id: string): Promise<IDocument> => {
        const res = await ginApiService<{ data: IDocument }>(`${this.BASE_URL}/${id}`)
        return res.data
    }

    // POST - Create document
    static createDocument = async (title: string, content: string) => {
        const res = await ginApiService(`${this.BASE_URL}`, {
            method: 'POST',
            body: JSON.stringify({ title, content })
        })
        return res.data
    }

    // PATCH - Update document
    static updateDocument = async (id: string, data: Partial<IDocument>) => {
        const res = await ginApiService(`${this.BASE_URL}/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        })
        return res.data
    }

    // DELETE - Delete document
    static deleteDocument = async (id: string) => {
        const res = await ginApiService(`${this.BASE_URL}/${id}`, {
            method: 'DELETE'
        })
        return res.data
    }
}
```

### Component with Multiple Operations (With i18n)

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../../../stores/notification/notification.selector'
import DocumentService from '../../../services/gin/document.service'

const DocumentList: React.FC = () => {
    const { t } = useTranslation('document') // IMPORTANT: Add useTranslation
    const notify = useNotify()
    const queryClient = useQueryClient()

    // Query for list
    const queryDocuments = useQuery({
        queryKey: ['documents'],
        queryFn: () => DocumentService.getDocuments()
    })

    // Mutation for create
    const mutationCreate = useMutation({
        mutationFn: ({ title, content }: { title: string; content: string }) =>
            DocumentService.createDocument(title, content),
        onSuccess: () => {
            notify(t('create.success'), 'success') // Use t()
            queryClient.invalidateQueries(['documents'])
        },
        onError: () => {
            notify(t('create.error'), 'error') // Use t()
        }
    })

    // Mutation for update
    const mutationUpdate = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<IDocument> }) =>
            DocumentService.updateDocument(id, data),
        onSuccess: () => {
            notify(t('update.success'), 'success') // Use t()
            queryClient.invalidateQueries(['documents'])
        },
        onError: () => {
            notify(t('update.error'), 'error') // Use t()
        }
    })

    // Mutation for delete
    const mutationDelete = useMutation({
        mutationFn: (id: string) => DocumentService.deleteDocument(id),
        onSuccess: () => {
            notify(t('delete.success'), 'success') // Use t()
            queryClient.invalidateQueries(['documents'])
        },
        onError: () => {
            notify(t('delete.error'), 'error') // Use t()
        }
    })

    const handleCreate = (title: string, content: string) => {
        mutationCreate.mutate({ title, content })
    }

    const handleUpdate = (id: string, data: Partial<IDocument>) => {
        mutationUpdate.mutate({ id, data })
    }

    const handleDelete = (id: string) => {
        mutationDelete.mutate(id)
    }

    if (queryDocuments.isPending) return <CircularProgress />
    if (queryDocuments.isError) return <Typography color="error">Error loading documents</Typography>

    return (
        <div>
            {queryDocuments.data?.map(doc => (
                <div key={doc.id}>
                    <Typography>{doc.title}</Typography>
                    <Button onClick={() => handleUpdate(doc.id, { title: 'New Title' })}>
                        {t('actions.update')}
                    </Button>
                    <Button onClick={() => handleDelete(doc.id)}>
                        {t('actions.delete')}
                    </Button>
                </div>
            ))}
            <Button onClick={() => handleCreate('New Doc', 'Content')}>
                {t('actions.createNew')}
            </Button>
        </div>
    )
}
```

**Corresponding i18n file:**

```json
// src/i18n/locales/en/document.json
{
    "create": {
        "success": "Document created successfully",
        "error": "Failed to create document"
    },
    "update": {
        "success": "Document updated successfully",
        "error": "Failed to update document"
    },
    "delete": {
        "success": "Document deleted successfully",
        "error": "Failed to delete document"
    },
    "actions": {
        "update": "Update",
        "delete": "Delete",
        "createNew": "Create New"
    }
}
```

## Example 3: File Upload Service

### Service with FormData

```typescript
// src/services/gin/upload.service.ts
export default class UploadService {
    private static readonly BASE_URL = '/upload'

    static uploadFile = async (file: File) => {
        const formData = new FormData()
        formData.append('file', file)

        const res = await ginApiService(`${this.BASE_URL}`, {
            method: 'POST',
            body: formData // ginApiService handles FormData automatically
        })
        return res.data
    }
}
```

### Component with File Upload (With i18n)

```typescript
const UploadPage: React.FC = () => {
    const { t } = useTranslation('upload') // IMPORTANT: Add useTranslation
    const notify = useNotify()

    const mutationUpload = useMutation({
        mutationFn: (file: File) => UploadService.uploadFile(file),
        onSuccess: (data) => {
            notify(t('success.fileUploaded'), 'success') // Use t()
            console.log('File URL:', data.url)
        },
        onError: () => {
            notify(t('error.uploadFailed'), 'error') // Use t()
        }
    })

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (file) {
            mutationUpload.mutate(file)
        }
    }

    return (
        <div>
            <input
                type="file"
                onChange={handleFileChange}
                disabled={mutationUpload.isPending}
            />
            {mutationUpload.isPending && <CircularProgress />}
        </div>
    )
}
```

**Corresponding i18n file:**

```json
// src/i18n/locales/en/upload.json
{
    "success": {
        "fileUploaded": "File uploaded successfully"
    },
    "error": {
        "uploadFailed": "Upload failed"
    }
}
```

## Example 4: Query with Parameters

### Service with Filters

```typescript
interface DocumentFilter {
    status?: string
    createdBy?: string
    startDate?: string
    endDate?: string
}

export default class DocumentService {
    static searchDocuments = async (filters: DocumentFilter): Promise<IDocument[]> => {
        const queryParams = new URLSearchParams()
        if (filters.status) queryParams.append('status', filters.status)
        if (filters.createdBy) queryParams.append('createdBy', filters.createdBy)
        if (filters.startDate) queryParams.append('startDate', filters.startDate)
        if (filters.endDate) queryParams.append('endDate', filters.endDate)

        const res = await ginApiService<{ data: IDocument[] }>(`${this.BASE_URL}?${queryParams.toString()}`)
        return res.data
    }
}
```

### Component with Filters

```typescript
const DocumentSearch: React.FC = () => {
    const [filters, setFilters] = useState<DocumentFilter>({ status: 'active' })

    const queryDocuments = useQuery({
        queryKey: ['documents', filters], // Include filters in key for proper caching
        queryFn: () => DocumentService.searchDocuments(filters),
        enabled: !!filters.status // Only run when filters are set
    })

    const handleFilterChange = (newFilters: DocumentFilter) => {
        setFilters(newFilters) // This will automatically refetch
    }

    return (
        <div>
            <FilterForm filters={filters} onChange={handleFilterChange} />
            {queryDocuments.data?.map(doc => (
                <div key={doc.id}>{doc.title}</div>
            ))}
        </div>
    )
}
```
