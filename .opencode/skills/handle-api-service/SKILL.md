---
name: handle-api-service
description: Guide for creating API service functions following project patterns. Use when creating new API endpoints, service functions, or integrating backend APIs with React Query (TanStack Query). Includes patterns for GET (useQuery), POST/PUT/PATCH/DELETE (useMutation), type definitions, error handling, notification integration, and i18n support. IMPORTANT - This project uses i18n, so all notification messages must use useTranslation hook and t() function (see i18n.mdc rule).
---

# API Service Handler

This skill provides the standardized pattern for creating API service functions and integrating them with TanStack Query in React components.

**IMPORTANT:** This project uses **react-i18next** for internationalization. All notification messages MUST use `useTranslation` hook and `t()` function. See `i18n.mdc` rule for detailed guidelines.

## Quick Reference

**Service Function Pattern:**

```typescript
// In services/gin/[domain].service.ts
static functionName = async (params): Promise<ReturnType> => {
    const res = await ginApiService<ResponseType>(`${this.BASE_URL}/endpoint`, {
        method: 'POST', // Omit for GET
        body: JSON.stringify(data) // Only for POST/PUT/PATCH/DELETE
    })
    return res.data
}
```

**Component Integration:**

- GET: `const queryName = useQuery({ queryKey, queryFn })`
- POST/PUT/PATCH/DELETE: `const mutationName = useMutation({ mutationFn, onSuccess, onError })`

## Core Rules

1. **GET requests**: Do NOT specify `method: 'GET'` (it's the default)
2. **useQuery**: Do NOT use `onError` or `onSuccess` callbacks - handle errors in the service function if needed
3. **useMutation**: DO use `onSuccess` and `onError` with `notify` for user feedback
4. **Naming convention**: `query[Feature]` for GET, `mutation[Feature]` for mutations
5. **Types**: Define in `types/common.ts` or inline with service
6. **i18n**: Check if project has `src/i18n/` folder - if yes, MUST use `useTranslation` hook and `t()` function for all notification messages (follow i18n.mdc rule)

## Pattern Details

### 1. Define Types (if needed)

```typescript
// In src/types/common.ts
export interface IUser {
    name: string
    email: string
}
```

### 2. Create Service Function

```typescript
// In src/services/gin/auth.service.ts
import { ginApiService } from '.'
import type { IUser } from '../../types/common'

export default class AuthService {
    private static readonly BASE_URL = '/auth'

    // GET request - no method specified
    static getProfile = async (): Promise<IUser> => {
        const res = await ginApiService<{ data: IUser }>(`${this.BASE_URL}/profile`)
        return res.data
    }

    // POST request - method required
    static login = async (username: string, password: string) => {
        const res = await ginApiService(`${this.BASE_URL}/login`, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        })
        return res.data
    }
}
```

### 3. Integrate with Component

#### For GET (useQuery):

```typescript
import { useQuery } from '@tanstack/react-query'
import AuthService from '../../../services/gin/auth.service'

const Component: React.FC = () => {
    const queryUserProfile = useQuery({
        queryKey: ['userProfile'],
        queryFn: () => AuthService.getProfile(),
        retry: 1
    })

    if (queryUserProfile.isPending) return <CircularProgress />
    if (queryUserProfile.isError) return <Error />

    const user = queryUserProfile.data
    return <div>{user?.name}</div>
}
```

**Key points:**

- Name: `query[Feature]`
- No `onError` or `onSuccess`
- Handle loading/error states in component
- Access data via `.data` property

#### For POST/PUT/PATCH/DELETE (useMutation):

**Without i18n:**

```typescript
import { useMutation } from '@tanstack/react-query'
import { useNotify } from '../../../stores/notification/notification.selector'
import AuthService from '../../../services/gin/auth.service'

const Component: React.FC = () => {
    const notify = useNotify()

    const mutationLogin = useMutation({
        mutationFn: (data: LoginFormData) => AuthService.login(data.username, data.password),
        onSuccess: (data) => {
            notify('Login successful', 'success')
            // Additional success logic (navigation, state updates, etc.)
        },
        onError: () => {
            notify('Login failed', 'error')
        }
    })

    const handleSubmit = (data: LoginFormData) => {
        mutationLogin.mutate(data)
    }
}
```

**With i18n (if project has `src/i18n/` folder):**

```typescript
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../../../stores/notification/notification.selector'
import AuthService from '../../../services/gin/auth.service'

const Component: React.FC = () => {
    const { t } = useTranslation('auth') // Specify namespace
    const notify = useNotify()

    const mutationLogin = useMutation({
        mutationFn: (data: LoginFormData) => AuthService.login(data.username, data.password),
        onSuccess: (data) => {
            notify(t('login.success.loginSuccess'), 'success')
            // Additional success logic (navigation, state updates, etc.)
        },
        onError: () => {
            notify(t('login.error.invalidCredentials'), 'error')
        }
    })

    const handleSubmit = (data: LoginFormData) => {
        mutationLogin.mutate(data)
    }
}
```

**Key points:**

- Name: `mutation[Feature]`
- MUST have `onSuccess` and `onError`
- MUST use `notify` for user feedback
- Import `useNotify` hook
- Trigger with `.mutate(data)`
- **If project has i18n**: Import `useTranslation`, use `t()` for all messages, follow i18n.mdc rule

## Complete Example

### Step 1: Define Type

```typescript
// src/types/common.ts
export interface IDocument {
    id: string
    title: string
    status: string
}
```

### Step 2: Create Service

```typescript
// src/services/gin/document.service.ts
import { ginApiService } from '.'
import type { IDocument } from '../../types/common'

export default class DocumentService {
    private static readonly BASE_URL = '/documents'

    static getDocument = async (id: string): Promise<IDocument> => {
        const res = await ginApiService<{ data: IDocument }>(`${this.BASE_URL}/${id}`)
        return res.data
    }

    static createDocument = async (title: string) => {
        const res = await ginApiService(`${this.BASE_URL}`, {
            method: 'POST',
            body: JSON.stringify({ title })
        })
        return res.data
    }

    static updateDocument = async (id: string, data: Partial<IDocument>) => {
        const res = await ginApiService(`${this.BASE_URL}/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        })
        return res.data
    }

    static deleteDocument = async (id: string) => {
        const res = await ginApiService(`${this.BASE_URL}/${id}`, {
            method: 'DELETE'
        })
        return res.data
    }
}
```

### Step 3: Use in Component

**Without i18n:**

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNotify } from '../../../stores/notification/notification.selector'
import DocumentService from '../../../services/gin/document.service'

const DocumentPage: React.FC = () => {
    const notify = useNotify()

    // GET - query pattern
    const queryDocument = useQuery({
        queryKey: ['document', documentId],
        queryFn: () => DocumentService.getDocument(documentId),
        enabled: !!documentId
    })

    // POST - mutation pattern
    const mutationCreate = useMutation({
        mutationFn: (title: string) => DocumentService.createDocument(title),
        onSuccess: () => {
            notify('Document created successfully', 'success')
            queryClient.invalidateQueries(['documents'])
        },
        onError: () => {
            notify('Failed to create document', 'error')
        }
    })

    // PATCH - mutation pattern
    const mutationUpdate = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<IDocument> }) =>
            DocumentService.updateDocument(id, data),
        onSuccess: () => {
            notify('Document updated successfully', 'success')
        },
        onError: () => {
            notify('Failed to update document', 'error')
        }
    })

    // DELETE - mutation pattern
    const mutationDelete = useMutation({
        mutationFn: (id: string) => DocumentService.deleteDocument(id),
        onSuccess: () => {
            notify('Document deleted successfully', 'success')
        },
        onError: () => {
            notify('Failed to delete document', 'error')
        }
    })
}
```

**With i18n (if project has `src/i18n/` folder):**

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../../../stores/notification/notification.selector'
import DocumentService from '../../../services/gin/document.service'

const DocumentPage: React.FC = () => {
    const { t } = useTranslation('document') // Specify appropriate namespace
    const notify = useNotify()

    // GET - query pattern
    const queryDocument = useQuery({
        queryKey: ['document', documentId],
        queryFn: () => DocumentService.getDocument(documentId),
        enabled: !!documentId
    })

    // POST - mutation pattern
    const mutationCreate = useMutation({
        mutationFn: (title: string) => DocumentService.createDocument(title),
        onSuccess: () => {
            notify(t('create.success'), 'success')
            queryClient.invalidateQueries(['documents'])
        },
        onError: () => {
            notify(t('create.error'), 'error')
        }
    })

    // PATCH - mutation pattern
    const mutationUpdate = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<IDocument> }) =>
            DocumentService.updateDocument(id, data),
        onSuccess: () => {
            notify(t('update.success'), 'success')
        },
        onError: () => {
            notify(t('update.error'), 'error')
        }
    })

    // DELETE - mutation pattern
    const mutationDelete = useMutation({
        mutationFn: (id: string) => DocumentService.deleteDocument(id),
        onSuccess: () => {
            notify(t('delete.success'), 'success')
        },
        onError: () => {
            notify(t('delete.error'), 'error')
        }
    })
}
```

## Common Patterns

### Query with Parameters

```typescript
const queryDocuments = useQuery({
    queryKey: ['documents', filters],
    queryFn: () => DocumentService.getDocuments(filters),
    enabled: !!filters // Only run when filters exist
})
```

### Mutation with Form Data

**Without i18n:**

```typescript
const mutationUpload = useMutation({
    mutationFn: (formData: FormData) => DocumentService.uploadFile(formData),
    onSuccess: () => {
        notify('File uploaded successfully', 'success')
        form.reset()
    },
    onError: () => {
        notify('Upload failed', 'error')
    }
})
```

**With i18n:**

```typescript
const { t } = useTranslation('upload')

const mutationUpload = useMutation({
    mutationFn: (formData: FormData) => DocumentService.uploadFile(formData),
    onSuccess: () => {
        notify(t('success.fileUploaded'), 'success')
        form.reset()
    },
    onError: () => {
        notify(t('error.uploadFailed'), 'error')
    }
})
```

### Cache Invalidation

```typescript
import { useQueryClient } from '@tanstack/react-query'

const queryClient = useQueryClient()

const mutationUpdate = useMutation({
    mutationFn: (data) => Service.update(data),
    onSuccess: () => {
        queryClient.invalidateQueries(['documents']) // Refetch related queries
    }
})
```

## Error Handling

**For useQuery:**

- Errors are handled in component via `isError` state
- No `onError` callback needed
- If custom error handling needed, implement in service function

**For useMutation:**

- Always use `onError` with `notify`
- Provide clear error messages to users
- Consider specific error types if needed

## Best Practices

1. **Consistent naming**: Use descriptive names that reflect the action
2. **Type safety**: Always define return types for service functions
3. **User feedback**: Every mutation should notify success/error
4. **Cache management**: Invalidate queries after mutations when data changes
5. **Loading states**: Handle `isLoading` for better UX
6. **Error states**: Always handle `isError` gracefully

## Checklist

When creating a new API service function:

- [ ] Check if project has `src/i18n/` folder
- [ ] Type defined in `types/common.ts` (if reusable)
- [ ] Service function created as `static async`
- [ ] GET requests omit `method` parameter
- [ ] Mutations specify correct HTTP method
- [ ] Component uses correct hook (`useQuery` vs `useMutation`)
- [ ] Query named `query[Feature]`
- [ ] Mutation named `mutation[Feature]`
- [ ] Mutations have `onSuccess` and `onError`
- [ ] `notify` imported and used in mutations
- [ ] **If i18n exists**: `useTranslation` hook imported and used for all messages
- [ ] **If i18n exists**: Translation keys added to appropriate locale JSON files
- [ ] **If i18n exists**: Follow i18n.mdc rule for translation structure
- [ ] Loading/error states handled in component
- [ ] Cache invalidation added if needed
